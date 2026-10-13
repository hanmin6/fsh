<?php
namespace Espo\Custom\Tools\Fusanhe;
use DateTimeImmutable;
use DateTimeZone;

/** Stateless, China-local day classification; company exceptions win. */
final class ReceptionSchedule
{
    public static function defaults(): array
    {
        return ['enabled' => false, 'timezone' => 'Asia/Shanghai', 'workdayStart' => '19:00',
            'workdayEnd' => '09:00', 'restdayAllDay' => true, 'dateOverrides' => [],
            'revision' => 0, 'activatedAt' => null];
    }
    public static function calendar(): array
    {
        return json_decode(file_get_contents(__DIR__ . '/../../Resources/autoReplyCalendar.json'), true, 512, JSON_THROW_ON_ERROR);
    }
    public static function validate(array $input): array
    {
        foreach (['enabled', 'restdayAllDay'] as $key) if (!is_bool($input[$key] ?? null)) throw new \InvalidArgumentException($key . ' must be boolean.');
        foreach (['workdayStart', 'workdayEnd'] as $key) if (!is_string($input[$key] ?? null) || !preg_match('/^(?:[01][0-9]|2[0-3]):[0-5][0-9]$/D', $input[$key])) throw new \InvalidArgumentException('Time must be HH:MM.');
        if ($input['workdayStart'] === $input['workdayEnd']) throw new \InvalidArgumentException('Start and end must differ.');
        $overrides = $input['dateOverrides'] ?? [];
        if (!is_array($overrides) || count($overrides) > 730) throw new \InvalidArgumentException('Invalid date overrides.');
        $clean = [];
        foreach ($overrides as $date => $kind) {
            $parsed = DateTimeImmutable::createFromFormat('!Y-m-d', (string) $date);
            if (!$parsed || $parsed->format('Y-m-d') !== $date || !in_array($kind, ['work', 'rest'], true)) throw new \InvalidArgumentException('Override must contain a valid date and work/rest.');
            $clean[$date] = $kind;
        }
        ksort($clean);
        return ['enabled' => $input['enabled'], 'timezone' => 'Asia/Shanghai', 'workdayStart' => $input['workdayStart'],
            'workdayEnd' => $input['workdayEnd'], 'restdayAllDay' => $input['restdayAllDay'], 'dateOverrides' => $clean];
    }
    public static function state(array $config, ?DateTimeImmutable $now = null): array
    {
        $local = ($now ?? new DateTimeImmutable('now'))->setTimezone(new DateTimeZone('Asia/Shanghai'));
        $date = $local->format('Y-m-d'); $calendar = self::calendar();
        $kind = $config['dateOverrides'][$date] ?? null;
        $covered = in_array((int) $local->format('Y'), $calendar['years'], true) || $kind !== null;
        if ($kind === null) {
            $kind = (int) $local->format('N') >= 6 ? 'rest' : 'work';
            foreach ($calendar['restRanges'] as [$start, $end]) if ($date >= $start && $date <= $end) $kind = 'rest';
            if (in_array($date, $calendar['workDates'], true)) $kind = 'work';
        }
        $time = $local->format('H:i'); $start = $config['workdayStart']; $end = $config['workdayEnd'];
        $inWindow = $start > $end ? ($time >= $start || $time < $end) : ($time >= $start && $time < $end);
        $active = !empty($config['enabled']) && $covered && (($kind === 'rest' && $config['restdayAllDay']) || $inWindow);
        return ['active' => $active, 'dayKind' => $kind, 'calendarCovered' => $covered, 'localNow' => $local->format('Y-m-d H:i:s'),
            'calendarYears' => $calendar['years'], 'calendarVersion' => $calendar['version'], 'calendarSource' => $calendar['source']];
    }
    /** Unknown human origin is conservative: never reclaim an existing takeover. */
    public static function allows(array $conversation, ?array $customer, array $config, ?DateTimeImmutable $now = null): bool
    {
        if (!self::state($config, $now)['active'] || ($conversation['status'] ?? '') === 'closed') return false;
        if (($conversation['controlMode'] ?? '') === 'human' && ($conversation['controlOrigin'] ?? '') !== 'valueRouting') return false;
        if ($customer && (!empty($customer['fusanheDoNotContact']) || in_array($customer['fusanheContactPolicy'] ?? '', ['optedOut','restricted'], true))) return false;
        if ($customer && !empty(((array)($customer['fusanheSalesProfile'] ?? []))['paused'])) return false;
        return true;
    }
}
