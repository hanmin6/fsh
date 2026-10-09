<?php
/** Import a prepared private manifest using Espo repositories and existing file storage.
 * Usage: php import_knowledge_library.php /container/path/prepared.json apply|verify
 * Source files are copied and verified in chunks. Existing records are never overwritten.
 */
require '/var/www/html/bootstrap.php';

$manifest = json_decode(file_get_contents($argv[1]), true, flags: JSON_THROW_ON_ERROR);
$mode = $argv[2] ?? 'verify';
if (!in_array($mode, ['apply', 'verify'], true)) throw new RuntimeException('Invalid mode');
$app = new Espo\Core\Application();
$container = $app->getContainer();
$factory = $container->get('injectableFactory');
$factory->create(Espo\Core\ApplicationUser::class)->setupSystemUser();
set_exception_handler(function (Throwable $error): void {
    fwrite(STDERR, get_class($error) . ': ' . $error->getMessage() . "\n");
    exit(1);
});
$em = $container->get('entityManager');
$storage = $factory->create(Espo\Core\FileStorage\Manager::class);
$statePath = dirname($argv[1]) . '/import-state.json';
$state = is_file($statePath) ? json_decode(file_get_contents($statePath), true, flags: JSON_THROW_ON_ERROR) : [];
$state += ['files' => [], 'products' => [], 'specs' => [], 'mediaFolders' => []];
$created = [];
$checkpoint = function () use (&$state, $statePath) {
    file_put_contents($statePath . '.tmp', json_encode($state, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE | JSON_THROW_ON_ERROR));
    rename($statePath . '.tmp', $statePath);
};
$make = function (string $type, array $values) use ($em, &$created) {
    $entity = $em->getNewEntity($type);
    $entity->set($values);
    $em->saveEntity($entity);
    $created[$type] = ($created[$type] ?? 0) + 1;
    return $entity;
};
$read = function (string $type, string $id) use ($em) {
    $entity = $em->getEntityById($type, $id);
    if (!$entity) throw new RuntimeException('Missing imported ' . $type);
    return $entity;
};
$relatedIds = function (string $type, $entity) use ($em): array {
    $ids = [];
    foreach ($em->getRDBRepository($type)->getRelation($entity, 'files')->find() as $attachment) $ids[] = $attachment->getId();
    return $ids;
};

foreach ($manifest['products'] as $p) {
    if (isset($state['products'][$p['name']])) {
        $entity = $read('FusanheProduct', $state['products'][$p['name']]);
        if ($entity->get('name') !== $p['name']) throw new RuntimeException('Product verification failed');
        continue;
    }
    if ($mode !== 'apply') throw new RuntimeException('Missing product mapping');
    $code = 'KB-' . substr(hash('sha256', $p['name']), 0, 12);
    $entity = $em->getRDBRepository('FusanheProduct')->where(['code' => $code])->findOne();
    if (!$entity) $entity = $make('FusanheProduct', ['name' => $p['name'], 'code' => $code, 'status' => 'enabled',
        'category' => $p['category'], 'description' => "共享盘产品信息表导入。具体配料和包装见各条待审核规格。\n来源：\n" . implode("\n", $p['sources'])]);
    $state['products'][$p['name']] = $entity->getId();
    $checkpoint();
}
foreach ($manifest['specs'] as $s) {
    if (isset($state['specs'][$s['key']])) {
        $entity = $read('FusanheProductSpec', $state['specs'][$s['key']]);
        foreach (['packingSpec', 'ingredients', 'cartonSpec'] as $field) {
            if (($entity->get($field) ?? '') !== $s[$field]) throw new RuntimeException('Spec field differs: ' . $field);
        }
        if ($entity->get('productId') !== $state['products'][$s['product']] || $entity->get('status') !== 'draft' ||
            json_decode($entity->get('internalNotes'), true, flags: JSON_THROW_ON_ERROR) !== $s['sourceCells']) throw new RuntimeException('Spec evidence differs');
        continue;
    }
    if ($mode !== 'apply') throw new RuntimeException('Missing spec mapping');
    $productId = $state['products'][$s['product']];
    $version = 'import-' . substr($s['key'], 0, 16);
    $entity = $em->getRDBRepository('FusanheProductSpec')->where(['productId' => $productId, 'version' => $version])->findOne();
    if (!$entity) $entity = $make('FusanheProductSpec', ['name' => $s['name'], 'productId' => $productId,
        'version' => $version, 'status' => 'draft', 'packingSpec' => $s['packingSpec'],
        'ingredients' => $s['ingredients'], 'cartonSpec' => $s['cartonSpec'], 'source' => mb_substr($s['sources'][0], 0, 255),
        'description' => "产品信息表原始行。重量、体积和海关编码保留在原始单元格中，待确认其业务含义。\n来源：\n" . implode("\n", $s['sources']),
        'internalNotes' => json_encode($s['sourceCells'], JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE | JSON_THROW_ON_ERROR)]);
    $state['specs'][$s['key']] = $entity->getId();
    $checkpoint();
}

$canonical = [];
$aliases = [];
$categoryRank = ['素材' => 0, '知识文档' => 1, '商品与规格' => 2, '证书与报告' => 3];
foreach ($manifest['files'] as $f) {
    $hash = $f['sha256'];
    $aliases[$hash][] = $f['origin'] ?? $f['source'];
    if (!isset($canonical[$hash])) $canonical[$hash] = $f;
    elseif ($categoryRank[$f['category']] > $categoryRank[$canonical[$hash]['category']]) $canonical[$hash]['category'] = $f['category'];
}
$hashAttachments = [];
foreach (array_values($canonical) as $i => $f) {
    $key = hash('sha256', $f['source']);
    $entry = $state['files'][$key] ?? [];
    $category = $f['category'];
    $source = $f['source'];
    $name = basename($source);
    $provenance = "来源：\n" . implode("\n", array_unique($aliases[$f['sha256']])) . "\nSHA-256：" . $f['sha256'];
    if (!isset($entry['attachmentId'])) {
        if ($mode !== 'apply') throw new RuntimeException('Missing attachment mapping');
        // A stable marker makes recovery safe even after a process stops before checkpointing.
        $marker = 'kb-import-' . substr($key, 0, 24);
        $a = $em->getRDBRepository('Attachment')->where(['storageFilePath' => $marker])->findOne();
        $duplicate = $hashAttachments[$f['sha256']] ?? null;
        if (!$a) $a = $make('Attachment', ['name' => $name, 'type' => $f['mime'], 'size' => $f['size'],
            'role' => 'Attachment', 'storage' => 'EspoUploadDir', 'storageFilePath' => $marker, 'isBeingUploaded' => !$duplicate,
            'sourceId' => $duplicate, 'global' => false]);
        $entry['attachmentId'] = $a->getId();
        $entry['sha256'] = $f['sha256'];
        $state['files'][$key] = $entry;
        $checkpoint();
    }
    if (($entry['sha256'] ?? null) !== $f['sha256']) throw new RuntimeException('Source changed; use a new reviewed import');
    $a = $read('Attachment', $entry['attachmentId']);
    $hashAttachments[$f['sha256']] = $a->getSourceId();
    $path = $storage->getLocalFilePath($a);
    if (!is_file($path) || $a->get('isBeingUploaded')) {
        if ($mode !== 'apply') throw new RuntimeException('Attachment file unavailable');
        $object = $f['container_object'];
        if (hash_file('sha256', $object) !== $f['sha256']) throw new RuntimeException('Staged file checksum mismatch');
        if (!copy($object, $path . '.kb-part') || hash_file('sha256', $path . '.kb-part') !== $f['sha256']) {
            throw new RuntimeException('File copy failed checksum verification');
        }
        rename($path . '.kb-part', $path);
        $a->set('isBeingUploaded', false);
        $em->saveEntity($a);
    }
    if (filesize($path) !== $f['size'] || hash_file('sha256', $path) !== $f['sha256']) throw new RuntimeException('Stored file differs');
    if ($category !== '素材') {
        $filePath = '/var/www/html/knowledge/imported-' . substr($key, 0, 24) . '/' . $name;
        if (!isset($entry['documentId'])) {
            if ($mode !== 'apply') throw new RuntimeException('Missing document mapping');
            $doc = $em->getRDBRepository('KnowledgeDocument')->where(['filePath' => $filePath])->findOne();
            $ext = strtolower(pathinfo($name, PATHINFO_EXTENSION));
            $types = ['pdf' => 'PDF', 'docx' => 'DOCX', 'xlsx' => 'XLSX', 'md' => 'Markdown', 'txt' => 'TXT'];
            $text = $f['extractedText'] ?? '';
            if (!$doc) $doc = $make('KnowledgeDocument', ['name' => $name, 'filePath' => $filePath,
                'category' => $category, 'sourceType' => $types[$ext] ?? 'Other', 'version' => 'import-' . substr($f['sha256'], 0, 12),
                'approvalStatus' => 'draft', 'checksum' => $f['sha256'], 'indexedAt' => gmdate('Y-m-d H:i:s'),
                'extractedText' => mb_substr($text, 0, 200000),
                'description' => $provenance . "\n文本提取：" . ($f['extraction'] ?? 'original_only') . (mb_strlen($text) > 200000 ? "\n全文较长，展示前20万字符；完整内容见原件。" : ''),
                'filesIds' => [$a->getId()]]);
            $entry['documentId'] = $doc->getId();
            $state['files'][$key] = $entry;
            $checkpoint();
        }
        $doc = $read('KnowledgeDocument', $entry['documentId']);
        $missingSources = array_filter($aliases[$f['sha256']], fn ($origin) => !str_contains($doc->get('description') ?? '', $origin));
        if ($missingSources) {
            if ($mode !== 'apply') throw new RuntimeException('Missing duplicate source provenance');
            $doc->set('description', ($doc->get('description') ?? '') . "\n相同原件的其他来源：\n" . implode("\n", $missingSources));
            $em->saveEntity($doc);
        }
        $files = $relatedIds('KnowledgeDocument', $doc);
        if (!in_array($a->getId(), $files, true)) {
            if ($mode !== 'apply') throw new RuntimeException('Missing document original link');
            $doc->set('filesIds', array_merge($files, [$a->getId()]));
            $em->saveEntity($doc);
        }
        // Keep a path-backed original so later scanner runs see the same checksum.
        if ($mode === 'apply' && !is_file($filePath)) {
            if (!is_dir(dirname($filePath))) mkdir(dirname($filePath), 0755, true);
            if (!copy($path, $filePath)) throw new RuntimeException('Knowledge original copy failed');
        }
        if (!is_file($filePath) || hash_file('sha256', $filePath) !== $f['sha256']) throw new RuntimeException('Knowledge checksum mismatch');
        if ($doc->get('checksum') !== $f['sha256'] || $doc->get('approvalStatus') !== 'draft' ||
            ($doc->get('extractedText') ?? '') !== mb_substr($f['extractedText'] ?? '', 0, 200000)) throw new RuntimeException('Knowledge text differs');
        if ($category === '证书与报告' && !isset($entry['certificateId'])) {
            if ($mode !== 'apply') throw new RuntimeException('Missing certificate mapping');
            $type = str_contains(strtolower($name), 'iso22000') || str_contains(strtolower($name), 'iso-22000') ? 'iso22000' :
                (str_contains($source, '官检报告') ? 'testReport' : (str_contains($name, '三证') ? 'businessLicense' : 'other'));
            $cert = $em->getRDBRepository('FusanheCertificate')->where(['notes' => '[knowledge-import:' . $key . ']'])->findOne();
            if (!$cert) $cert = $make('FusanheCertificate', ['name' => $name, 'type' => $type, 'status' => 'draft',
                'description' => $provenance . "\n有效期、签发机构和适用范围需核对原件。", 'notes' => '[knowledge-import:' . $key . ']',
                'filesIds' => []]);
            $entry['certificateId'] = $cert->getId();
            $state['files'][$key] = $entry;
            $checkpoint();
            // Each relation has its own attachment record; both reference one stored original.
            $ca = $make('Attachment', ['name' => $name, 'type' => $f['mime'], 'size' => $f['size'], 'role' => 'Attachment',
                'storage' => 'EspoUploadDir', 'sourceId' => $a->getSourceId(), 'global' => false]);
            $cert->set('filesIds', [$ca->getId()]);
            $em->saveEntity($cert);
            $entry['certificateAttachmentId'] = $ca->getId();
        }
        if (isset($entry['certificateId']) && !isset($entry['certificateAttachmentId'])) {
            if ($mode !== 'apply') throw new RuntimeException('Certificate attachment incomplete');
            $cert = $read('FusanheCertificate', $entry['certificateId']);
            $attached = $relatedIds('FusanheCertificate', $cert);
            if (!$attached) {
                $ca = $make('Attachment', ['name' => $name, 'type' => $f['mime'], 'size' => $f['size'], 'role' => 'Attachment',
                    'storage' => 'EspoUploadDir', 'sourceId' => $a->getSourceId(), 'global' => false]);
                $cert->set('filesIds', [$ca->getId()]);
                $em->saveEntity($cert);
                $attached = [$ca->getId()];
            }
            $entry['certificateAttachmentId'] = $attached[0];
        }
        if (isset($entry['certificateAttachmentId'])) {
            $cert = $read('FusanheCertificate', $entry['certificateId']);
            $ca = $read('Attachment', $entry['certificateAttachmentId']);
            if ($cert->get('status') !== 'draft' || !in_array($ca->getId(), $relatedIds('FusanheCertificate', $cert), true) ||
                hash_file('sha256', $storage->getLocalFilePath($ca)) !== $f['sha256']) throw new RuntimeException('Certificate original differs');
        }
    } else {
        // Attach media to a browsable folder document so normal record ACL applies.
        $folder = explode('/', $f['relative_path'])[0];
        if (!isset($state['mediaFolders'][$folder])) {
            if ($mode !== 'apply') throw new RuntimeException('Missing media folder');
            $folderPath = 'media-index/' . hash('sha256', $folder);
            $doc = $em->getRDBRepository('KnowledgeDocument')->where(['filePath' => $folderPath])->findOne();
            if (!$doc) $doc = $make('KnowledgeDocument', ['name' => $folder . ' · 素材目录', 'filePath' => $folderPath,
                'category' => '素材目录', 'sourceType' => 'Other', 'approvalStatus' => 'draft', 'version' => 'import-1',
                'description' => '收录商品图、视频、设计稿与网站素材，原文件可从附件下载。']);
            $state['mediaFolders'][$folder] = $doc->getId();
            $checkpoint();
        }
        $folderDoc = $read('KnowledgeDocument', $state['mediaFolders'][$folder]);
        if ($a->get('parentId') !== $folderDoc->getId() || $a->get('parentType') !== 'KnowledgeDocument' || $a->get('field') !== 'files') {
            if ($mode !== 'apply') throw new RuntimeException('Media folder relation differs');
            $a->set(['parentId' => $folderDoc->getId(), 'parentType' => 'KnowledgeDocument', 'field' => 'files', 'relatedId' => null, 'relatedType' => null]);
            $em->saveEntity($a);
        }
    }
    $entry['verified'] = true;
    $state['files'][$key] = $entry;
    if ($mode === 'apply') $checkpoint();
    if (($i + 1) % 50 === 0) echo json_encode(['mode' => $mode, 'files' => $i + 1, 'total' => count($canonical)]) . "\n";
}
foreach ($manifest['files'] as $f) {
    $canonicalKey = hash('sha256', $canonical[$f['sha256']]['source']);
    $aliasKey = hash('sha256', $f['source']);
    $state['files'][$aliasKey] = $state['files'][$canonicalKey];
}
foreach ($state['mediaFolders'] as $folder => $id) {
    $lines = [];
    foreach ($manifest['files'] as $f) {
        if ($canonical[$f['sha256']]['category'] !== '素材' || explode('/', $canonical[$f['sha256']]['relative_path'])[0] !== $folder) continue;
        $lines[] = ($f['origin'] ?? $f['source']) . "\nSHA-256: " . $f['sha256'];
    }
    $text = mb_substr(implode("\n\n", $lines), 0, 200000);
    $doc = $read('KnowledgeDocument', $id);
    if ($mode === 'apply' && ($doc->get('extractedText') ?? '') !== $text) {
        $doc->set('extractedText', $text);
        $em->saveEntity($doc);
    }
    if (($doc->get('extractedText') ?? '') !== $text) throw new RuntimeException('Media source index differs');
}
if ($mode === 'apply') $checkpoint();
$report = ['mode' => $mode, 'sourceFiles' => count($manifest['files']), 'uniqueFiles' => count($canonical), 'files' => count($state['files']), 'products' => count($state['products']),
    'specs' => count($state['specs']), 'created' => $created];
echo json_encode($report, JSON_UNESCAPED_UNICODE | JSON_THROW_ON_ERROR) . "\n";
file_put_contents(dirname($argv[1]) . '/' . $mode . '-report.json', json_encode($report, JSON_PRETTY_PRINT | JSON_THROW_ON_ERROR));
