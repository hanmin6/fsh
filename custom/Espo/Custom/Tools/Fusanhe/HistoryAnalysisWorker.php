<?php
namespace Espo\Custom\Tools\Fusanhe;

use Espo\ORM\Entity;
use Espo\ORM\EntityManager;

final class HistoryAnalysisWorker
{
    public function __construct(private EntityManager $em, private ServiceKernel $kernel, private HistoryAiProvider $provider) {}

    /** Streaming local summarization: hash every message, send only bounded categorical evidence. */
    public function snapshot(Entity $conversation): array
    {
        $hash = hash_init('sha256');
        hash_update($hash, HistorySignals::VERSION . '|' . (string) getenv('AI_MODEL'));
        $counts = ['inbound' => 0, 'outbound' => 0]; $buckets = []; $last = null;
        for ($offset = 0; ; $offset += 200) {
            $rows = $this->em->getRDBRepository('ExternalMessage')->where(['conversationId' => $conversation->getId()])
                ->order('sentAt')->order('id')->limit($offset, 200)->find();
            foreach ($rows as $m) {
                $direction = $m->get('direction') === 'inbound' ? 'inbound' : 'outbound';
                $counts[$direction]++;
                hash_update($hash, json_encode([$m->getId(), $direction, $m->get('sentAt'), $m->get('body')], JSON_THROW_ON_ERROR));
                $last = ['id' => $m->getId(), 'direction' => $direction, 'signals' => []];
                foreach (HistorySignals::signals((string) $m->get('body')) as $signal) {
                    $key = $direction . ':' . $signal;
                    if (!isset($buckets[$key])) $buckets[$key] = ['count' => 0, 'firstId' => $m->getId()];
                    $buckets[$key]['count']++;
                    $buckets[$key]['lastId'] = $m->getId();
                }
            }
            if (count($rows) < 200) break;
        }
        $evidence = []; $map = [];
        $add = function (string $id, string $direction, array $signals, int $count) use (&$evidence, &$map) {
            $ref = 'm' . (count($map) + 1); $map[$ref] = $id;
            $evidence[] = ['ref' => $ref, 'direction' => $direction, 'signals' => $signals, 'occurrences' => $count];
        };
        foreach ($buckets as $key => $bucket) {
            [$direction, $signal] = explode(':', $key);
            $add($bucket['firstId'], $direction, [$signal], $bucket['count']);
            if ($bucket['firstId'] !== $bucket['lastId']) $add($bucket['lastId'], $direction, [$signal], $bucket['count']);
        }
        if ($last) $add($last['id'], $last['direction'], [], 1);
        return ['version' => hash_final($hash), 'map' => $map,
            'input' => ['messageCounts' => $counts, 'evidence' => $evidence]];
    }

    public function run(int $maxCalls, bool $retry, callable $progress, callable $reserve): array
    {
        $stats = ['scanned' => 0, 'cached' => 0, 'completed' => 0, 'failed' => 0, 'calls' => 0, 'usageTokens' => 0];
        $channels = [];
        foreach ($this->em->getRDBRepository('ExternalChannel')->where(['type' => 'Alibaba'])->find() as $c) $channels[] = $c->getId();
        if (!$channels) return $stats;
        for ($offset = 0; ; $offset += 100) {
            $rows = $this->kernel->repo('ExternalConversation')->where(['channelId' => $channels, 'lastSourceSyncAt!=' => null])->order('id')->limit($offset, 100)->find();
            foreach ($rows as $c) {
                $stats['scanned']++;
                $snap = $this->snapshot($c);
                if ($c->get('insightsVersion') === $snap['version'] && $c->get('insightsStatus') === 'completed') { $stats['cached']++; continue; }
                if ($c->get('insightsStatus') === 'failed' && !$retry && $c->get('insightsVersion') === $snap['version']) continue;
                if ($stats['calls'] >= $maxCalls || !$reserve()) return $stats;
                $stats['calls']++;
                $c->set(['insightsVersion' => $snap['version'], 'insightsStatus' => 'pending', 'insightsData' => null, 'insightsError' => null]);
                $this->kernel->save($c, ['fusanheInsights' => true]);
                try {
                    if (!$snap['map']) throw new \RuntimeException('no_source_messages');
                    $result = $this->provider->analyze($snap['input']);
                    $stats['usageTokens'] += $result['usageTokens'];
                    $result['evidenceMessageIds'] = array_values(array_unique(array_map(fn($ref) => $snap['map'][$ref], $result['evidenceMessageIds'])));
                    $result['promptVersion'] = HistorySignals::VERSION;
                    $result['sourceMessageCount'] = array_sum($snap['input']['messageCounts']);
                    $result['analyzedAt'] = $this->kernel->now();
                    // New messages arriving during a model request must invalidate this result.
                    $current = $this->snapshot($c);
                    $state = $current['version'] === $snap['version'] ? 'completed' : 'stale';
                    $result['status'] = $state;
                    $c->set(['insightsData' => $result, 'insightsStatus' => $state,
                        'insightsAt' => $result['analyzedAt'], 'insightsModel' => $result['model']]);
                    $stats['completed'] += (int) ($state === 'completed');
                } catch (\Throwable $e) {
                    $safe = ['ai_not_configured','ai_transport_failed','ai_response_too_large','ai_invalid_json','ai_invalid_schema','ai_invalid_evidence','ai_unsupported_products','no_source_messages'];
                    $c->set(['insightsStatus' => 'failed', 'insightsError' => in_array($e->getMessage(), $safe, true) ? $e->getMessage() : 'analysis_failed']);
                    $stats['failed']++;
                }
                $this->kernel->save($c, ['fusanheInsights' => true]);
                $this->kernel->audit('history.analysis', 'system', 'history-worker', 'ExternalConversation', $c->getId(), $c->get('insightsStatus'),
                    ['version' => $snap['version'], 'promptVersion' => HistorySignals::VERSION, 'errorCode' => $c->get('insightsError')]);
                $progress($stats);
            }
            if (count($rows) < 100) return $stats;
        }
    }
}
