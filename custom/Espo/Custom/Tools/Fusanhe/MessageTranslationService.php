<?php
namespace Espo\Custom\Tools\Fusanhe;

use Espo\ORM\EntityManager;

/** Server-owned derived text: never changes originals or creates outbound activity. */
final class MessageTranslationService
{
    private const CACHE = 'data/fusanhe-message-translations';
    public function __construct(private EntityManager $em, private TextGateway $text) {}

    public function translate(string $conversationId, array $ids, bool $retry = false): array
    {
        if (!is_dir(self::CACHE) && !mkdir(self::CACHE, 0700, true) && !is_dir(self::CACHE)) throw new \RuntimeException('translation_storage_failed');
        $lock = fopen(self::CACHE . '/' . hash('sha256', $conversationId) . '.lock', 'c');
        if (!$lock || !flock($lock, LOCK_EX | LOCK_NB)) {
            if ($lock) fclose($lock);
            return ['messages' => array_map(fn($id) => ['id' => $id, 'status' => 'busy'], $ids)];
        }
        try { return $this->locked($conversationId, $ids, $retry); }
        finally { flock($lock, LOCK_UN); fclose($lock); }
    }

    private function locked(string $conversationId, array $ids, bool $retry): array
    {
        $results = []; $pending = []; $units = [];
        foreach ($ids as $id) {
            $entity = $this->em->getEntityById('ExternalMessage', $id);
            if (!$entity || $entity->get('conversationId') !== $conversationId) throw new \RuntimeException('translation_invalid_message');
            $body = (string) $entity->get('body');
            if (trim((string) $entity->get('translatedBody')) !== '') {
                $results[$id] = ['id' => $id, 'status' => 'completed', 'translatedBody' => $entity->get('translatedBody')]; continue;
            }
            $key = hash('sha256', 'v1:' . $id . ':' . $body); $path = self::CACHE . '/' . $key . '.json';
            $cached = is_file($path) ? json_decode((string) file_get_contents($path), true) : null;
            if (is_array($cached) && (in_array($cached['status'] ?? '', ['completed','skipped'], true) || (!$retry && ($cached['at'] ?? 0) > time() - 600))) {
                if (($cached['status'] ?? '') === 'completed') {
                    $entity->set('translatedBody', $cached['translatedBody']); $this->em->saveEntity($entity, ['fusanheService' => true]);
                }
                unset($cached['at']); $results[$id] = ['id' => $id] + $cached; continue;
            }
            if (!MessageTranslationPolicy::candidate($body)) {
                $results[$id] = ['id' => $id, 'status' => 'skipped']; $this->cache($path, ['status' => 'skipped']); continue;
            }
            try { $chunks = MessageTranslationPolicy::chunks($body); }
            catch (\RuntimeException $error) { $results[$id] = ['id' => $id, 'status' => 'failed', 'errorCode' => $error->getMessage()]; continue; }
            $pending[$id] = ['entity' => $entity, 'body' => $body, 'path' => $path, 'units' => []];
            foreach ($chunks as $part) {
                $unit = 'part-' . count($units); $units[] = ['id' => $unit, 'body' => $part, 'messageId' => $id]; $pending[$id]['units'][] = $unit;
            }
        }
        $translated = [];
        while ($units) {
            $batch = []; $bytes = 0;
            while ($units && count($batch) < 6) {
                $next = $units[0];
                if (isset($results[$next['messageId']])) { array_shift($units); continue; }
                if ($batch && $bytes + strlen($next['body']) > 12000) break;
                $batch[] = array_shift($units); $bytes += strlen($next['body']);
            }
            if (!$batch) continue;
            $input = array_map(fn($r) => ['id' => $r['id'], 'body' => $r['body']], $batch);
            try {
                $response = $this->text->complete([
                    ['role' => 'system', 'content' => MessageTranslationPolicy::prompt()],
                    ['role' => 'user', 'content' => json_encode(['messages' => $input], JSON_THROW_ON_ERROR | JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES)],
                ], null, true, 8192);
                $validated = MessageTranslationPolicy::validate(json_decode($response['content'], true), $input);
                $translated += $validated;
            } catch (\Throwable $error) {
                $safe = ['text_not_configured','text_auth_failed','text_rate_limited','text_transport_failed','text_incomplete_response','text_model_mismatch','translation_invalid_response'];
                $code = in_array($error->getMessage(), $safe, true) ? $error->getMessage() : 'translation_failed';
                foreach ($batch as $unit) {
                    $id = $unit['messageId']; $results[$id] = ['id' => $id, 'status' => 'failed', 'errorCode' => $code];
                    $this->cache($pending[$id]['path'], ['status' => 'failed', 'errorCode' => $code]);
                }
            }
        }
        foreach ($pending as $id => $item) {
            if (isset($results[$id])) continue;
            $parts = []; $english = false;
            foreach ($item['units'] as $unit) {
                $english = $english || $translated[$unit]['english'];
                $parts[] = $translated[$unit]['english'] ? $translated[$unit]['translatedBody'] : $this->originalPart($item['body'], $item['units'], $unit);
            }
            $value = $english ? ['status' => 'completed', 'translatedBody' => implode("\n", $parts)] : ['status' => 'skipped'];
            $fresh = $this->em->getEntityById('ExternalMessage', $id);
            if (!$fresh || $fresh->get('body') !== $item['body'] || $fresh->get('conversationId') !== $conversationId) {
                $results[$id] = ['id' => $id, 'status' => 'failed', 'errorCode' => 'translation_message_changed']; continue;
            }
            // Cache first so a failed database save can replay without another paid request.
            $this->cache($item['path'], $value);
            if ($english) { $fresh->set('translatedBody', $value['translatedBody']); $this->em->saveEntity($fresh, ['fusanheService' => true]); }
            $results[$id] = ['id' => $id] + $value;
        }
        return ['messages' => array_map(fn($id) => $results[$id], $ids)];
    }

    private function originalPart(string $body, array $ids, string $unit): string
    {
        return MessageTranslationPolicy::chunks($body)[array_search($unit, $ids, true)];
    }

    private function cache(string $path, array $value): void
    {
        $temporary = $path . '.' . bin2hex(random_bytes(6)) . '.tmp';
        if (file_put_contents($temporary, json_encode($value + ['at' => time()], JSON_THROW_ON_ERROR | JSON_UNESCAPED_UNICODE), LOCK_EX) === false) throw new \RuntimeException('translation_storage_failed');
        chmod($temporary, 0600);
        if (!rename($temporary, $path)) { unlink($temporary); throw new \RuntimeException('translation_storage_failed'); }
    }
}
