<?php
namespace Espo\Custom\Tools\Fusanhe;

/** Private atomic records, shared by the CRM web and scheduler containers. */
final class MorningReportStore
{
    public static function validDate(string $date): bool
    {
        $d = \DateTimeImmutable::createFromFormat('!Y-m-d', $date);
        return $d && $d->format('Y-m-d') === $date;
    }
    public function directory(): string
    {
        $dir = ReceptionSettings::directory() . '/morning-reports';
        if (!is_dir($dir) && !mkdir($dir, 0700) && !is_dir($dir)) throw new \RuntimeException('report_storage_unavailable');
        ReceptionSettings::protect($dir, 0700); return $dir;
    }
    public function exclusive(callable $fn, bool $wait = true): mixed
    {
        $path = $this->directory() . '/worker.lock'; $lock = fopen($path, 'c');
        if (!$lock) throw new \RuntimeException('report_storage_unavailable');
        ReceptionSettings::protect($path, 0600);
        if (!flock($lock, LOCK_EX | ($wait ? 0 : LOCK_NB))) { fclose($lock); return ['busy' => true]; }
        try { return $fn(); } finally { flock($lock, LOCK_UN); fclose($lock); }
    }
    private function write(string $path, array $value): void
    {
        $tmp = tempnam($this->directory(), 'report-');
        if (!$tmp) throw new \RuntimeException('report_storage_unavailable');
        try {
            ReceptionSettings::protect($tmp, 0600);
            if (file_put_contents($tmp, json_encode($value, JSON_UNESCAPED_UNICODE | JSON_THROW_ON_ERROR)) === false || !rename($tmp, $path)) throw new \RuntimeException('report_storage_unavailable');
        } finally { if (is_file($tmp)) unlink($tmp); }
    }
    public function settings(): array
    {
        $path = $this->directory() . '/settings.json';
        return (is_file($path) ? json_decode(file_get_contents($path), true, 128, JSON_THROW_ON_ERROR) : []) +
            ['enabled' => false, 'timezone' => 'Asia/Shanghai', 'sendTime' => '09:00', 'firstDate' => null, 'updatedAt' => null];
    }
    public function configure(bool $enabled, \DateTimeImmutable $now): array
    {
        return $this->exclusive(function () use ($enabled, $now) {
            $settings = $this->settings();
            if ($enabled && !$settings['enabled']) {
                $local = $now->setTimezone(new \DateTimeZone('Asia/Shanghai'));
                $settings['firstDate'] = ($local->format('H:i') >= '09:00' ? $local->modify('+1 day') : $local)->format('Y-m-d');
            }
            $settings['enabled'] = $enabled; $settings['updatedAt'] = $now->setTimezone(new \DateTimeZone('UTC'))->format('c');
            $this->write($this->directory() . '/settings.json', $settings); return $settings;
        });
    }
    public function read(string $date): ?array
    {
        if (!self::validDate($date)) throw new \InvalidArgumentException('invalid_report_date');
        $path = $this->directory() . '/' . $date . '.json';
        return is_file($path) ? json_decode(file_get_contents($path), true, 128, JSON_THROW_ON_ERROR) : null;
    }
    public function save(array $report): void
    {
        if (!self::validDate($report['date'] ?? '')) throw new \InvalidArgumentException('invalid_report_date');
        $this->write($this->directory() . '/' . $report['date'] . '.json', $report);
    }
    public function dates(): array
    {
        $dates = [];
        foreach (glob($this->directory() . '/????-??-??.json') ?: [] as $path) {
            $date = basename($path, '.json'); if (self::validDate($date)) $dates[] = $date;
        }
        rsort($dates); return array_slice($dates, 0, 90);
    }
}
