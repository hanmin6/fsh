<?php
namespace Espo\Custom\Tools\Fusanhe;
use Espo\Core\Exceptions\BadRequest;
use Espo\Core\Exceptions\Conflict;

/** Atomic persistent settings, shared by web/daemon containers via CRM data. */
final class ReceptionSettings
{
    public function __construct(private ServiceKernel $kernel) {}
    public static function path(): string { return 'data/fusanhe/auto-reply.json'; }
    public static function protect(string $path, int $mode): void
    {
        $parent = stat('data'); clearstatcache(true, $path); $stat = stat($path);
        if (!$parent || !$stat || ($stat['uid'] !== $parent['uid'] && !chown($path, $parent['uid'])) ||
            ($stat['gid'] !== $parent['gid'] && !chgrp($path, $parent['gid'])) || !chmod($path, $mode)) throw new \RuntimeException('Reception storage permissions unavailable.');
    }
    public static function directory(): string
    {
        $dir = dirname(self::path());
        if (!is_dir($dir) && !mkdir($dir, 0700, true) && !is_dir($dir)) throw new \RuntimeException('Reception storage unavailable.');
        self::protect($dir, 0700); return $dir;
    }
    public static function read(): array
    {
        $path = self::path();
        if (!is_file($path)) return ReceptionSchedule::defaults();
        return json_decode(file_get_contents($path), true, 512, JSON_THROW_ON_ERROR) + ReceptionSchedule::defaults();
    }
    public function update(array $input, string $actor): array
    {
        try { $validated = ReceptionSchedule::validate($input); }
        catch (\InvalidArgumentException $e) { throw new BadRequest($e->getMessage()); }
        $dir = self::directory();
        $lock = fopen($dir . '/auto-reply-settings.lock', 'c');
        if ($lock) self::protect($dir . '/auto-reply-settings.lock', 0600);
        if (!$lock || !flock($lock, LOCK_EX)) throw new \RuntimeException('Settings lock unavailable.');
        try {
            $old = self::read();
            if (($input['revision'] ?? null) !== $old['revision']) throw new Conflict('Settings changed; reload before saving.');
            $new = $validated + ['revision' => $old['revision'] + 1, 'activatedAt' => $old['activatedAt'], 'updatedAt' => gmdate('Y-m-d H:i:s')];
            if ($new['enabled'] && !$old['enabled']) $new['activatedAt'] = gmdate('Y-m-d H:i:s');
            $tmp = tempnam($dir, 'schedule-');
            try {
                if (file_put_contents($tmp, json_encode($new, JSON_UNESCAPED_UNICODE | JSON_THROW_ON_ERROR)) === false) throw new \RuntimeException('Settings write failed.');
                self::protect($tmp, 0600);
                if (!rename($tmp, self::path())) throw new \RuntimeException('Settings commit failed.');
            } finally { if (is_file($tmp)) unlink($tmp); }
            $this->kernel->audit('reception.settings', 'user', $actor, 'ExternalConversation', 'schedule', 'success',
                ['revision' => $new['revision'], 'enabled' => $new['enabled'], 'workdayStart' => $new['workdayStart'], 'workdayEnd' => $new['workdayEnd'], 'restdayAllDay' => $new['restdayAllDay'], 'overrideCount' => count($new['dateOverrides'])]);
            return $new;
        } finally { flock($lock, LOCK_UN); fclose($lock); }
    }
}
