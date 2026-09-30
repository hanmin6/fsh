<?php
namespace Espo\Custom\Tools\Fusanhe;

/** Bounded TLS transfers. Returned CDN URLs get no API key, redirects or private IP access. */
class MediaNetwork
{
    public function publicUrl(string $url): array
    {
        if (strlen($url) > 2048 || preg_match('/[\x00-\x20\x7f]/', $url)) throw new \RuntimeException('media_invalid_url');
        $parts = parse_url($url);
        $host = strtolower((string) ($parts['host'] ?? ''));
        if (($parts['scheme'] ?? '') !== 'https' || $host === '' || isset($parts['user']) || isset($parts['pass']) || isset($parts['fragment']) || (isset($parts['port']) && $parts['port'] !== 443) || filter_var($host, FILTER_VALIDATE_IP)) throw new \RuntimeException('media_invalid_url');
        $addresses = gethostbynamel($host);
        if (!$addresses) throw new \RuntimeException('media_invalid_url');
        foreach ($addresses as $address) {
            if (!filter_var($address, FILTER_VALIDATE_IP, FILTER_FLAG_NO_PRIV_RANGE | FILTER_FLAG_NO_RES_RANGE) || str_starts_with($address, '169.254.') || str_starts_with($address, '127.') || str_starts_with($address, '192.0.0.') || str_starts_with($address, '198.18.') || str_starts_with($address, '198.19.') || ((ip2long($address) & 0xffc00000) === 0x64400000)) throw new \RuntimeException('media_invalid_url');
        }
        return ['host' => $host, 'address' => $addresses[0]];
    }
    public function json(string $method, string $url, string $key, ?array $body = null): array
    {
        return $this->request($method, $url, $key, $body, 1024 * 1024, true);
    }
    public function download(string $url, string $expectedMime): array
    {
        $result = $this->request('GET', $url, null, null, 25 * 1024 * 1024, false);
        $mime = strtolower(trim(explode(';', $result['mime'])[0]));
        if ($expectedMime === 'video/mp4' && $mime !== 'video/mp4' && $mime !== 'application/octet-stream') throw new \RuntimeException('media_invalid_result');
        if ($expectedMime === 'image' && !in_array($mime, ['image/png', 'image/jpeg', 'image/webp', 'application/octet-stream'], true)) throw new \RuntimeException('media_invalid_result');
        if ($expectedMime === 'image') {
            $info = @getimagesizefromstring($result['bytes']);
            $mime = $info['mime'] ?? '';
        } else { $mime = 'video/mp4'; }
        return ['bytes' => $result['bytes'], 'mime' => $mime];
    }
    private function request(string $method, string $url, ?string $key, ?array $body, int $limit, bool $json): array
    {
        $destination = $this->publicUrl($url);
        // Credentials are exclusively scoped to TokenDance API requests.
        if ($key !== null && $destination['host'] !== 'tokendance.space') throw new \RuntimeException('media_invalid_provider');
        $curl = curl_init($url);
        $bytes = '';
        $headers = ['Accept: application/json'];
        if ($key !== null) $headers[] = 'Authorization: Bearer ' . $key;
        if ($body !== null) $headers[] = 'Content-Type: application/json';
        curl_setopt_array($curl, [CURLOPT_CUSTOMREQUEST => $method, CURLOPT_HTTPHEADER => $headers,
            CURLOPT_RETURNTRANSFER => false, CURLOPT_CONNECTTIMEOUT => 10, CURLOPT_TIMEOUT => $method === 'POST' ? 90 : 40,
            CURLOPT_FOLLOWLOCATION => false, CURLOPT_PROTOCOLS => CURLPROTO_HTTPS,
            CURLOPT_SSL_VERIFYPEER => true, CURLOPT_SSL_VERIFYHOST => 2,
            CURLOPT_RESOLVE => [$destination['host'] . ':443:' . $destination['address']],
            CURLOPT_WRITEFUNCTION => static function ($handle, string $chunk) use (&$bytes, $limit): int {
                if (strlen($bytes) + strlen($chunk) > $limit) return 0;
                $bytes .= $chunk; return strlen($chunk);
            }]);
        if ($body !== null) curl_setopt($curl, CURLOPT_POSTFIELDS, json_encode($body, JSON_THROW_ON_ERROR | JSON_UNESCAPED_UNICODE));
        $ok = curl_exec($curl);
        $status = curl_getinfo($curl, CURLINFO_RESPONSE_CODE);
        $mime = (string) curl_getinfo($curl, CURLINFO_CONTENT_TYPE);
        curl_close($curl);
        if ($method === 'POST' && in_array($status, [400, 401, 403, 404, 413, 415, 422, 429], true)) throw new MediaRejected('media_submission_rejected');
        if ($ok === false || $status < 200 || $status >= 300) throw new \RuntimeException('media_upstream_unavailable');
        if (!$json) return ['bytes' => $bytes, 'mime' => $mime];
        try { $decoded = json_decode($bytes, true, 24, JSON_THROW_ON_ERROR); }
        catch (\Throwable) { throw new \RuntimeException('media_invalid_response'); }
        if (!is_array($decoded)) throw new \RuntimeException('media_invalid_response');
        return $decoded;
    }
}
