"""Prepare a private, hash-verified library import without changing source files.

Run on the source server with a discovery manifest and an empty/private stage.
Only XML members of Office archives are parsed; embedded images stay in originals.
"""
import hashlib
import json
import mimetypes
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile

NS = {'m': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def worksheets(path):
    with zipfile.ZipFile(path) as z:
        strings = []
        if 'xl/sharedStrings.xml' in z.namelist():
            strings = [''.join(s.itertext()) for s in ET.fromstring(z.read('xl/sharedStrings.xml'))]
        rels = {r.attrib['Id']: r.attrib['Target'] for r in ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))}
        book = ET.fromstring(z.read('xl/workbook.xml'))
        result = []
        for sheet in book.find('m:sheets', NS):
            target = rels[sheet.attrib['{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id']]
            member = target.lstrip('/') if target.startswith('/') else 'xl/' + target
            root = ET.fromstring(z.read(member))
            rows = []
            for row in root.findall('.//m:row', NS):
                cells = {}
                for c in row.findall('m:c', NS):
                    v, inline = c.find('m:v', NS), c.find('m:is', NS)
                    value = v.text or '' if v is not None else ''.join(inline.itertext()) if inline is not None else ''
                    if c.get('t') == 's' and value:
                        value = strings[int(value)]
                    formula = c.find('m:f', NS)
                    if formula is not None:
                        value += ' [formula: ' + (formula.text or '') + ']'
                    if value:
                        cells[c.attrib['r']] = value
                if cells:
                    rows.append({'row': int(row.attrib['r']), 'cells': cells})
            merges = [m.attrib['ref'] for m in root.findall('m:mergeCells/m:mergeCell', NS)]
            result.append({'name': sheet.attrib['name'], 'rows': rows, 'mergedRanges': merges})
        return result


def extract(path):
    suffix = path.suffix.lower()
    if suffix == '.xlsx':
        sheets = worksheets(path)
        text = '\n\n'.join('工作表：' + s['name'] + '\n' + '\n'.join(
            ' | '.join(k + ': ' + v for k, v in row['cells'].items()) for row in s['rows']) for s in sheets)
        return text, sheets, 'cells_with_cached_values_and_formulas'
    if suffix == '.docx':
        with zipfile.ZipFile(path) as z:
            root = ET.fromstring(z.read('word/document.xml'))
            ns = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
            return '\n'.join(''.join(t.text or '' for t in p.iter(ns + 't')) for p in root.iter(ns + 'p')), [], 'paragraphs_and_table_paragraphs'
    if suffix == '.pdf':
        r = subprocess.run(['pdftotext', '-layout', str(path), '-'], capture_output=True, timeout=60)
        text = r.stdout.decode('utf-8', errors='replace')
        return text, [], 'pdf_text' if text.strip() else 'image_pdf_original_available'
    if suffix in ('.txt', '.md'):
        return path.read_text(errors='replace'), [], 'text'
    return '', [], 'original_only'


def prepare(manifest_path, stage, knowledge_root=None):
    os.umask(0o077)
    discovery = json.loads(manifest_path.read_text())
    stage.mkdir(parents=True, exist_ok=True)
    objects = stage / 'objects'
    objects.mkdir(exist_ok=True)
    files, products, specs, errors = [], {}, {}, []
    prior = json.loads((stage / 'prepared.json').read_text()) if (stage / 'prepared.json').exists() else {}
    cached = {f['source']: f for f in prior.get('files', [])}
    for i, item in enumerate(discovery['files'], 1):
        src = Path(item['source'])
        assert src.is_file() and not src.is_symlink(), 'Invalid source: ' + str(src)
        stat = src.stat()
        assert stat.st_size == item['size'], 'Source size changed: ' + str(src)
        sha = digest(src)
        destination = objects / sha
        if destination.exists():
            assert destination.stat().st_size == stat.st_size and digest(destination) == sha
        else:
            temp = destination.with_suffix('.part')
            shutil.copyfile(src, temp)
            assert digest(temp) == sha, 'Copy checksum mismatch'
            temp.replace(destination)
        assert src.stat().st_size == stat.st_size and src.stat().st_mtime_ns == stat.st_mtime_ns
        f = {**item, 'sha256': sha, 'object_path': str(destination), 'source_mtime_ns': stat.st_mtime_ns,
             'mime': mimetypes.guess_type(src.name)[0] or 'application/octet-stream'}
        if item['category'] != '素材':
            try:
                if cached.get(str(src), {}).get('sha256') == sha:
                    old = cached[str(src)]
                    text, sheets, mode = old['extractedText'], old.get('sheets', []), old['extraction']
                else:
                    text, sheets, mode = extract(src)
                f.update(extractedText=text, sheets=sheets, extraction=mode)
            except Exception as e:
                f.update(extractedText='', sheets=[], extraction='original_only')
                errors.append({'source': str(src), 'error': type(e).__name__})
            if '产品信息表' in src.name and src.suffix == '.xlsx':
                for sheet in f['sheets']:
                    sheet_name = sheet['name']
                    for row in sheet['rows']:
                        rn = row['row']
                        cells = {re.sub(r'\d+', '', k): v for k, v in row['cells'].items()}
                        if not cells.get('B') or not cells.get('C') or cells['B'] == '品名':
                            continue
                        products.setdefault(sheet_name, {'name': sheet_name, 'category': '食品原料与添加剂', 'sources': []})
                        source = str(src) + ' / ' + sheet_name + ' / 行' + str(rn)
                        if source not in products[sheet_name]['sources']:
                            products[sheet_name]['sources'].append(source)
                        # Identical rows in duplicate workbooks are one spec; changed rows stay distinct.
                        key = hashlib.sha256(json.dumps([sheet_name, cells], ensure_ascii=False, sort_keys=True).encode()).hexdigest()
                        spec = specs.setdefault(key, {'key': key, 'product': sheet_name, 'name': cells['B'],
                            'packingSpec': cells['C'], 'ingredients': cells.get('D', ''),
                            'cartonSpec': cells.get('K', ''), 'sourceCells': row['cells'], 'sources': []})
                        if source not in spec['sources']:
                            spec['sources'].append(source)
            if any(word in src.name.lower() for word in ['认证报告', '商标注册证']):
                f['category'] = '证书与报告'
            if knowledge_root:
                key = hashlib.sha256(str(src).encode()).hexdigest()
                original = knowledge_root / ('imported-' + key[:24]) / src.name
                original.parent.mkdir(parents=True, exist_ok=True)
                if original.exists():
                    assert digest(original) == sha
                else:
                    shutil.copyfile(destination, original)
                original.chmod(0o644)
                original.parent.chmod(0o755)
        f['container_object'] = '/var/www/html/data/knowledge-import/objects/' + sha
        files.append(f)
        if i % 50 == 0:
            print(json.dumps({'prepared': i, 'total': len(discovery['files'])}), flush=True)
    report = {'source_manifest': str(manifest_path), 'files': files,
              'products': list(products.values()), 'specs': list(specs.values()), 'extraction_errors': errors}
    tmp = stage / 'prepared.tmp'
    tmp.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    tmp.replace(stage / 'prepared.json')
    print(json.dumps({'prepared': len(files), 'uniqueObjects': len({f['sha256'] for f in files}),
                      'products': len(products), 'specs': len(specs), 'extractionErrors': errors}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    prepare(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]) if len(sys.argv) > 3 else None)
