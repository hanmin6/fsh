#!/usr/bin/env python3
"""Import reviewed private Lead manifests and original documents via Espo REST.

Credentials: ESPOCRM_ADMIN_USERNAME / ESPOCRM_ADMIN_PASSWORD.
Usage: python3 scripts/import_history.py private-manifest.json [--apply]
No outbound messages are created. Existing records are never overwritten.
Run only one importer at a time. Back up the CRM before --apply.
"""
import argparse
import base64
import json
import os
import re
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class Client:
    def __init__(self):
        self.base = os.environ.get('ESPOCRM_API_URL', 'http://127.0.0.1:8080/api/v1').rstrip('/')
        credentials = ':'.join(os.environ[k] for k in ('ESPOCRM_ADMIN_USERNAME', 'ESPOCRM_ADMIN_PASSWORD'))
        self.headers = {'Authorization': 'Basic ' + base64.b64encode(credentials.encode()).decode(),
                        'Content-Type': 'application/json'}

    def call(self, method, path, payload=None):
        body = json.dumps(payload, ensure_ascii=False).encode() if payload is not None else None
        with urlopen(Request(self.base + '/' + path, body, self.headers, method=method), timeout=60) as response:
            return json.load(response)

    def find(self, entity, field, marker, extra=()):
        conditions = [('contains', field, marker), *extra]
        params = {'maxSize': 2}
        for i, (operator, attribute, value) in enumerate(conditions):
            params.update({f'where[{i}][type]': operator, f'where[{i}][attribute]': attribute,
                           f'where[{i}][value]': value})
        found = self.call('GET', entity + '?' + urlencode(params))
        if found.get('total', len(found['list'])) > 1:
            raise RuntimeError('Ambiguous provenance marker: ' + marker)
        return found['list'][0] if found['list'] else None


def validate(records):
    seen = set()
    for record in records:
        key = record['key']
        if not re.fullmatch(r'[a-z0-9-]+', key) or key in seen:
            raise ValueError('Duplicate or invalid import key')
        seen.add(key)
        if not record['lead'].get('lastName') or not record['lead'].get('description'):
            raise ValueError('Lead name and reviewed description are required')
        if set(record['lead']) - {'firstName', 'lastName', 'status', 'source', 'addressCountry',
                                  'description', 'emailAddress', 'phoneNumber'}:
            raise ValueError('Unexpected Lead field')
        documents = record.get('documents', [])
        if len({d['name'] for d in documents}) != len(documents):
            raise ValueError('Document filenames must be unique within each Lead')
        for document in documents:
            base64.b64decode(document['base64'], validate=True)
            if not document.get('name') or not document.get('type'):
                raise ValueError('Document name/type required')


def run(records, client):
    result = []
    for record in records:
        marker = '[history-import:' + record['key'] + ']'
        lead = client.find('Lead', 'description', marker)
        created = lead is None
        if created:
            payload = dict(record['lead'])
            payload['description'] += '\n\n' + marker
            lead = client.call('POST', 'Lead', payload)
        note_marker = marker + ':originals'
        note = client.find('Note', 'post', note_marker,
                           [('equals', 'parentType', 'Lead'), ('equals', 'parentId', lead['id'])])
        if note is None:
            note = client.call('POST', 'Note', {'parentType': 'Lead', 'parentId': lead['id'],
                'post': note_marker + '\n历史资料原件；发送状态未知。', 'attachmentsIds': []})
        # Fetch latest attachment linkage to recover from an interrupted import.
        note = client.call('GET', 'Note/' + note['id'])
        ids = list(note.get('attachmentsIds') or [])
        names = note.get('attachmentsNames') or {}
        for document in record.get('documents', []):
            if document['name'] in names.values():
                continue
            attachment = client.call('POST', 'Attachment', {
                'name': document['name'], 'type': document['type'], 'role': 'Attachment',
                'relatedType': 'Note', 'relatedId': note['id'], 'field': 'attachments',
                'file': 'data:' + document['type'] + ';base64,' + document['base64']})
            ids.append(attachment['id'])
            note = client.call('PUT', 'Note/' + note['id'], {'attachmentsIds': ids})
            names = note.get('attachmentsNames') or names
        verified = client.call('GET', 'Note/' + note['id'])
        if len(verified.get('attachmentsIds') or []) != len(record.get('documents', [])):
            raise RuntimeError('Original document attachment verification failed')
        result.append({'key': record['key'], 'leadId': lead['id'], 'created': created,
                       'noteId': note['id'], 'attachments': len(ids)})
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    records = json.loads(args.manifest.read_text())
    validate(records)
    if not args.apply:
        print(json.dumps({'validated': len(records), 'documents': sum(len(r.get('documents', [])) for r in records)}))
        return
    print(json.dumps(run(records, Client()), ensure_ascii=False))


if __name__ == '__main__':
    main()
