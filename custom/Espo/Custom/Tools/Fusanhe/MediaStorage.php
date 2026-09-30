<?php
namespace Espo\Custom\Tools\Fusanhe;

/** Private, bounded files under Espo's protected data directory; never public storage URLs. */
final class MediaStorage
{
    private string $directory;
    public function __construct()
    {
        $this->directory = 'data/fusanhe-media';
        if (!is_dir($this->directory) && !mkdir($this->directory, 0700, true) && !is_dir($this->directory)) throw new \RuntimeException('media_storage_unavailable');
    }
    public function locked(callable $callback): mixed
    {
        $file = fopen($this->directory . '/submission.lock', 'c');
        if (!$file || !flock($file, LOCK_EX)) throw new \RuntimeException('media_lock_unavailable');
        try { return $callback(); } finally { flock($file, LOCK_UN); fclose($file); }
    }
    public function put(string $bytes): string
    {
        if (strlen($bytes) > 25 * 1024 * 1024) throw new \RuntimeException('media_result_too_large');
        $key = bin2hex(random_bytes(24));
        $path = $this->directory . '/' . $key . '.bin';
        if (file_put_contents($path, $bytes, LOCK_EX) !== strlen($bytes)) throw new \RuntimeException('media_storage_unavailable');
        chmod($path, 0600);
        return $key;
    }
    public function get(string $key): string
    {
        if (!preg_match('/^[a-f0-9]{48}$/D', $key)) throw new \RuntimeException('media_asset_missing');
        $value = @file_get_contents($this->directory . '/' . $key . '.bin');
        if ($value === false) throw new \RuntimeException('media_asset_missing');
        return $value;
    }
}
