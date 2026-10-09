<?php
namespace Espo\Custom\Tools\Fusanhe;

use DateTimeImmutable;
use DateTimeZone;

final class CardProgress
{
    public const DAILY_TARGET = 15;

    public static function bounds(DateTimeImmutable $now): array
    {
        $day = $now->setTimezone(new DateTimeZone('Asia/Shanghai'))->setTime(0, 0);
        $utc = new DateTimeZone('UTC');
        return [$day->setTimezone($utc), $day->modify('+1 day')->setTimezone($utc)];
    }

    /** Count distinct customers with confirmed deliveries, excluding simulations. */
    public static function summarize(iterable $events, DateTimeImmutable $now): array
    {
        [$start, $end] = self::bounds($now);
        $customers = [];
        $last = null;
        foreach ($events as $event) {
            if (($event['source'] ?? '') !== 'Muse' || ($event['direction'] ?? '') !== 'outbound' ||
                !in_array($event['deliveryStatus'] ?? '', ['sent', 'delivered'], true) ||
                empty($event['customerKey']) || empty($event['sentAt'])) continue;
            try {
                $at = new DateTimeImmutable($event['sentAt'], new DateTimeZone('UTC'));
            } catch (\Exception) {
                continue;
            }
            if ($at < $start || $at >= $end || $at > $now) continue;
            $customers[$event['customerKey']] = true;
            if ($last === null || $at > $last) $last = $at;
        }
        $count = count($customers);
        return [
            'date' => $now->setTimezone(new DateTimeZone('Asia/Shanghai'))->format('Y-m-d'),
            'timezone' => 'Asia/Shanghai', 'dailyTarget' => self::DAILY_TARGET,
            'todayCompleted' => $count, 'remaining' => max(0, self::DAILY_TARGET - $count),
            'lastSentAt' => $last?->setTimezone(new DateTimeZone('UTC'))->format('Y-m-d H:i:s'),
            'checkedAt' => $now->setTimezone(new DateTimeZone('UTC'))->format('Y-m-d H:i:s'),
        ];
    }
}
