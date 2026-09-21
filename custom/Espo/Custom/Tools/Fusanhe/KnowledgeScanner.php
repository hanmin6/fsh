<?php
namespace Espo\Custom\Tools\Fusanhe;

use Espo\ORM\EntityManager;
use FilesystemIterator;
use RecursiveDirectoryIterator;
use RecursiveIteratorIterator;
use RuntimeException;
use ZipArchive;

final class KnowledgeScanner
{
    private const TYPES = [
        'pdf' => 'PDF',
        'docx' => 'DOCX',
        'xlsx' => 'XLSX',
        'txt' => 'TXT',
        'md' => 'Markdown',
    ];

    public function __construct(private EntityManager $em) {}

    public function scan(): array
    {
        $configuredRoot = (string) (getenv('KNOWLEDGE_BASE_PATH') ?: '/var/www/html/knowledge');
        $root = realpath($configuredRoot);
        if ($root === false || !is_dir($root) || !is_readable($root)) {
            return ['scanned' => 0, 'updated' => 0, 'skipped' => 0, 'errors' => ['knowledge_root_unavailable']];
        }
        $root = rtrim($root, DIRECTORY_SEPARATOR);
        $maxBytes = max(1024, (int) (getenv('FUSANHE_KNOWLEDGE_MAX_BYTES') ?: 25 * 1024 * 1024));
        $scanned = 0;
        $updated = 0;
        $skipped = 0;
        $errors = [];
        $iterator = new RecursiveIteratorIterator(
            new RecursiveDirectoryIterator($root, FilesystemIterator::SKIP_DOTS)
        );

        foreach ($iterator as $file) {
            if (!$file->isFile()) {
                continue;
            }
            $ext = strtolower($file->getExtension());
            if (!isset(self::TYPES[$ext])) {
                $skipped++;
                continue;
            }
            $scanned++;
            $path = realpath($file->getPathname());
            $label = $this->safeLabel($root, $file->getPathname());
            try {
                if ($path === false || !$this->insideRoot($root, $path)) {
                    throw new RuntimeException('path_outside_root');
                }
                if (is_link($file->getPathname())) {
                    throw new RuntimeException('symlink_not_allowed');
                }
                $size = filesize($path);
                if ($size === false || $size > $maxBytes) {
                    throw new RuntimeException('file_too_large');
                }
                if (!is_readable($path)) {
                    throw new RuntimeException('file_not_readable');
                }
                $checksum = hash_file('sha256', $path);
                if ($checksum === false) {
                    throw new RuntimeException('checksum_failed');
                }

                $doc = $this->em->getRDBRepository('KnowledgeDocument')->where(['filePath' => $path])->findOne();
                $contentChanged = $doc && !hash_equals((string) $doc->get('checksum'), $checksum);
                if ($doc && !$contentChanged) {
                    continue;
                }
                if (!$doc) {
                    $doc = $this->em->getNewEntity('KnowledgeDocument');
                    $doc->set([
                        'name' => $file->getBasename(),
                        'filePath' => $path,
                        'sourceType' => self::TYPES[$ext],
                        'approvalStatus' => 'draft',
                        'version' => '1',
                    ]);
                }
                $doc->set([
                    'checksum' => $checksum,
                    'indexedAt' => gmdate('Y-m-d H:i:s'),
                    'extractedText' => $this->extract($path, $ext),
                ]);
                if ($contentChanged && $doc->get('approvalStatus') === 'approved') {
                    $doc->set('approvalStatus', 'draft');
                }
                $this->em->saveEntity($doc);
                $updated++;
            } catch (\Throwable $error) {
                $reason = $error instanceof RuntimeException ? $error->getMessage() : 'processing_failed';
                $errors[] = ['file' => $label, 'code' => $reason];
            }
        }
        return compact('scanned', 'updated', 'skipped', 'errors');
    }

    private function insideRoot(string $root, string $path): bool
    {
        return $path === $root || str_starts_with($path, $root . DIRECTORY_SEPARATOR);
    }

    private function safeLabel(string $root, string $path): string
    {
        $real = realpath($path);
        if ($real !== false && $this->insideRoot($root, $real)) {
            return ltrim(substr($real, strlen($root)), DIRECTORY_SEPARATOR);
        }
        return basename($path);
    }

    private function extract(string $path, string $ext): string
    {
        if (in_array($ext, ['txt', 'md'], true)) {
            return mb_substr((string) file_get_contents($path), 0, 200000);
        }
        if ($ext === 'pdf' && trim((string) shell_exec('command -v pdftotext 2>/dev/null')) !== '') {
            return mb_substr((string) shell_exec('pdftotext ' . escapeshellarg($path) . ' - 2>/dev/null'), 0, 200000);
        }
        if (in_array($ext, ['docx', 'xlsx'], true) && class_exists(ZipArchive::class)) {
            $zip = new ZipArchive();
            if ($zip->open($path) === true) {
                $names = $ext === 'docx' ? ['word/document.xml'] : ['xl/sharedStrings.xml'];
                $text = '';
                foreach ($names as $name) {
                    $xml = $zip->getFromName($name);
                    if ($xml !== false) {
                        $text .= ' ' . strip_tags(str_replace(['</w:p>', '</si>'], ["\n", "\n"], $xml));
                    }
                }
                $zip->close();
                return mb_substr(html_entity_decode($text), 0, 200000);
            }
        }
        return '';
    }
}
