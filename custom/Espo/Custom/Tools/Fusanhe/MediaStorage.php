<?php
namespace Espo\Custom\Tools\Fusanhe;

/** Private, bounded files under Espo's protected data directory; never public storage URLs. */
final class MediaStorage
{
    private string $directory;
    private int $owner;
    private int $group;
    public function __construct()
    {
        $this->directory = 'data/fusanhe-media';
        if (!is_dir($this->directory) && !mkdir($this->directory, 0700, true) && !is_dir($this->directory)) throw new \RuntimeException('media_storage_unavailable');
        $parent = stat(dirname($this->directory));
        if ($parent === false) throw new \RuntimeException('media_storage_unavailable');
        $this->owner = $parent['uid'];
        $this->group = $parent['gid'];
        $this->protect($this->directory, 0700);
    }
    public function locked(callable $callback): mixed
    {
        $file = fopen($this->directory . '/submission.lock', 'c');
        if (!$file) throw new \RuntimeException('media_lock_unavailable');
        try { $this->protect($this->directory . '/submission.lock', 0600); }
        catch (\Throwable $error) { fclose($file); throw $error; }
        if (!flock($file, LOCK_EX)) { fclose($file); throw new \RuntimeException('media_lock_unavailable'); }
        try { return $callback(); } finally { flock($file, LOCK_UN); fclose($file); }
    }
    public function put(string $bytes): string
    {
        if (strlen($bytes) > 25 * 1024 * 1024) throw new \RuntimeException('media_result_too_large');
        $key = bin2hex(random_bytes(24));
        $path = $this->directory . '/' . $key . '.bin';
        if (file_put_contents($path, $bytes, LOCK_EX) !== strlen($bytes)) throw new \RuntimeException('media_storage_unavailable');
        $this->protect($path, 0600);
        return $key;
    }
    public function get(string $key): string
    {
        if (!preg_match('/^[a-f0-9]{48}$/D', $key)) throw new \RuntimeException('media_asset_missing');
        $value = @file_get_contents($this->directory . '/' . $key . '.bin');
        if ($value === false) throw new \RuntimeException('media_asset_missing');
        return $value;
    }

    public function remove(string $key): void
    {
        if (!preg_match('/^[a-f0-9]{48}$/D', $key)) return;
        @unlink($this->directory . '/' . $key . '.bin');
    }

    /** Bearer capability for exactly one image, valid only until provider retrieval. */
    public function shareSource(string $key, string $mime, int $expires): string
    {
        if (!in_array($mime, ['image/png', 'image/jpeg', 'image/webp'], true)) throw new \RuntimeException('media_invalid_source');
        $this->get($key);
        $token = bin2hex(random_bytes(32));
        $path = $this->directory . '/source-' . hash('sha256', $token) . '.json';
        $value = json_encode(['key' => $key, 'mime' => $mime, 'expires' => $expires], JSON_THROW_ON_ERROR);
        if (file_put_contents($path, $value, LOCK_EX) !== strlen($value)) throw new \RuntimeException('media_storage_unavailable');
        $this->protect($path, 0600);
        return $token;
    }

    public function sharedSource(string $token): array
    {
        if (!preg_match('/^[a-f0-9]{64}$/D', $token)) throw new \RuntimeException('media_source_missing');
        $path = $this->directory . '/source-' . hash('sha256', $token) . '.json';
        $value = json_decode((string) @file_get_contents($path), true);
        if (!$value || ($value['expires'] ?? 0) <= time()) {
            @unlink($path);
            throw new \RuntimeException('media_source_missing');
        }
        if (!in_array($value['mime'] ?? '', ['image/png', 'image/jpeg', 'image/webp'], true)) throw new \RuntimeException('media_source_missing');
        return ['mime' => $value['mime'], 'bytes' => $this->get($value['key'])];
    }

    /** Root workers and web requests must share the data-volume owner, while files stay private. */
    private function protect(string $path, int $mode): void
    {
        clearstatcache(true, $path);
        $stat = stat($path);
        if ($stat === false ||
            ($stat['uid'] !== $this->owner && !chown($path, $this->owner)) ||
            ($stat['gid'] !== $this->group && !chgrp($path, $this->group)) ||
            !chmod($path, $mode)) throw new \RuntimeException('media_storage_unavailable');
    }
}
