<?php
namespace Espo\Custom\Tools\Fusanhe;

use DateTimeImmutable;
use DateTimeZone;

/** Acquisition counts use immutable Lead creation time, never message deliveries. */
final class CardProgress
{
    public static function bounds(DateTimeImmutable $now): array
    {
        $end = $now->setTimezone(new DateTimeZone('Asia/Shanghai'))->setTime(0, 0);
        $utc = new DateTimeZone('UTC');
        return [$end->modify('-1 day')->setTimezone($utc), $end->setTimezone($utc)];
    }

    public static function summarize(iterable $leads, DateTimeImmutable $now): array
    {
        [$start, $end] = self::bounds($now);
        $seen = []; $yesterday = 0; $last = null;
        $values = ['high' => 0, 'medium' => 0, 'low' => 0, 'unrated' => 0];
        $routes = ['human' => 0, 'ai' => 0, 'pending_rating' => 0, 'blocked' => 0];
        foreach ($leads as $lead) {
            $id = (string) ($lead['id'] ?? '');
            if (!$id || isset($seen[$id]) || empty($lead['fusanheSourceId']) ||
                !in_array($lead['fusanheSourceSystem'] ?? '', ['Muse', 'Xpoz', 'OpenOutreach'], true) ||
                empty($lead['createdAt'])) continue;
            try { $at = new DateTimeImmutable($lead['createdAt'], new DateTimeZone('UTC')); }
            catch (\Exception) { continue; }
            if ($at > $now) continue;
            $seen[$id] = true;
            $routes[AcquisitionRouting::route($lead)]++;
            if ($last === null || $at > $last) $last = $at;
            if ($at < $start || $at >= $end) continue;
            $yesterday++;
            $rating = AcquisitionRouting::effectiveRating($lead);
            $bucket = match ($rating) { 'S', 'A' => 'high', 'B' => 'medium', 'C', 'D' => 'low', default => 'unrated' };
            $values[$bucket]++;
        }
        return [
            'date' => $now->setTimezone(new DateTimeZone('Asia/Shanghai'))->format('Y-m-d'),
            'statisticsDate' => $start->setTimezone(new DateTimeZone('Asia/Shanghai'))->format('Y-m-d'),
            'timezone' => 'Asia/Shanghai', 'yesterdayAcquired' => $yesterday,
            'totalAcquired' => count($seen), 'yesterdayValueCounts' => $values, 'followUpCounts' => $routes,
            'lastAcquiredAt' => $last?->setTimezone(new DateTimeZone('UTC'))->format('Y-m-d H:i:s'),
            'checkedAt' => $now->setTimezone(new DateTimeZone('UTC'))->format('Y-m-d H:i:s'),
        ];
    }
}
