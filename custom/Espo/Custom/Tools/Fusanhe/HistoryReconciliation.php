<?php
namespace Espo\Custom\Tools\Fusanhe;

final class HistoryReconciliation
{
    /** Set equality, not matching totals: two different sets may have the same count. */
    public static function compare(array $manifest, array $actual): array
    {
        if (!isset($manifest['conversations']) || !is_array($manifest['conversations']) || !array_is_list($manifest['conversations'])) throw new \InvalidArgumentException('invalid_manifest');
        if (!isset($manifest['failed']) || !is_int($manifest['failed']) || $manifest['failed'] < 0) throw new \InvalidArgumentException('invalid_failure_count');
        $expected = []; $messagesMatch = true;
        foreach ($manifest['conversations'] as $c) {
            if (!is_array($c) || !isset($c['id'], $c['messageIds']) || !is_string($c['id']) || $c['id'] === '' || !is_array($c['messageIds']) || !array_is_list($c['messageIds']) || isset($expected[$c['id']])) throw new \InvalidArgumentException('invalid_source_ids');
            foreach ($c['messageIds'] as $mid) if (!is_string($mid) || $mid === '') throw new \InvalidArgumentException('invalid_message_ids');
            if (count(array_unique($c['messageIds'])) !== count($c['messageIds'])) throw new \InvalidArgumentException('duplicate_message_ids');
            $expected[$c['id']] = $c['messageIds'];
            $ids = $actual[$c['id']] ?? null;
            if ($ids === null || array_diff($ids, $c['messageIds']) || array_diff($c['messageIds'], $ids)) $messagesMatch = false;
        }
        $missing = count(array_diff(array_keys($expected), array_keys($actual)));
        $extra = count(array_diff(array_keys($actual), array_keys($expected)));
        $enumerated = ($manifest['enumerationComplete'] ?? false) === true;
        $historyComplete = ($manifest['historyComplete'] ?? false) === true;
        $complete = $enumerated && $historyComplete && $manifest['failed'] === 0 && $missing === 0 && $extra === 0 && $messagesMatch;
        return ['platformVisible' => $enumerated ? count($expected) : null, 'observedVisible' => count($expected),
            'failedSync' => $manifest['failed'], 'missingConversations' => $missing, 'extraConversations' => $extra,
            'messagesMatch' => $messagesMatch, 'reconciled' => $complete,
            'reason' => $complete ? '会话稳定 ID 与消息稳定 ID 集合已逐项对账，源端声明枚举和历史加载完整，失败为零。' : '覆盖未完成：请核对完整枚举、消息加载、失败数及会话/消息 ID 差集。'];
    }
}
