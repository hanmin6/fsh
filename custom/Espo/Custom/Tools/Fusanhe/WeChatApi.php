<?php
namespace Espo\Custom\Tools\Fusanhe;

/** Tencent iLink protocol as shipped by @tencent-weixin/openclaw-weixin 2.4.10. */
class WeChatApi
{
    public const BASE = 'https://ilinkai.weixin.qq.com';
    public static function trustedUrl(string $url): bool
    {
        $p = parse_url($url);
        $host = strtolower($p['host'] ?? '');
        return ($p['scheme'] ?? '') === 'https' && !isset($p['user']) && !isset($p['pass']) &&
            !isset($p['fragment']) && (!isset($p['port']) || $p['port'] === 443) &&
            ($host === 'weixin.qq.com' || str_ends_with($host, '.weixin.qq.com'));
    }
    public function request(string $method, string $base, string $endpoint, ?array $body = null, string $token = '', int $timeout = 10): array
    {
        if (!self::trustedUrl($base) || preg_match('/[\r\n]/', $token)) throw new \RuntimeException('untrusted_endpoint');
        $headers = ['iLink-App-Id: bot', 'iLink-App-ClientVersion: 132106', 'Accept: application/json'];
        if ($method === 'POST') {
            $headers[] = 'Content-Type: application/json';
            $headers[] = 'AuthorizationType: ilink_bot_token';
            $headers[] = 'X-WECHAT-UIN: ' . base64_encode((string) random_int(1, 2147483647));
            if ($token !== '') $headers[] = 'Authorization: Bearer ' . $token;
        }
        $ch = curl_init(rtrim($base, '/') . '/' . ltrim($endpoint, '/'));
        $text = '';
        curl_setopt_array($ch, [CURLOPT_CUSTOMREQUEST => $method, CURLOPT_HTTPHEADER => $headers,
            CURLOPT_CONNECTTIMEOUT => 5, CURLOPT_TIMEOUT => $timeout, CURLOPT_FOLLOWLOCATION => false,
            CURLOPT_SSL_VERIFYPEER => true, CURLOPT_SSL_VERIFYHOST => 2,
            CURLOPT_WRITEFUNCTION => static function ($handle, $chunk) use (&$text) {
                if (strlen($text) + strlen($chunk) > 1048576) return 0;
                $text .= $chunk; return strlen($chunk);
            }]);
        if ($body !== null) curl_setopt($ch, CURLOPT_POSTFIELDS, json_encode($body, JSON_THROW_ON_ERROR | JSON_UNESCAPED_UNICODE));
        $ok = curl_exec($ch); $errno = curl_errno($ch); $status = curl_getinfo($ch, CURLINFO_RESPONSE_CODE); curl_close($ch);
        if ($ok === false) throw new \RuntimeException($errno === CURLE_OPERATION_TIMEDOUT ? 'wechat_timeout' : 'wechat_unavailable');
        if ($status < 200 || $status >= 300) throw new \RuntimeException('wechat_unavailable');
        try { $data = json_decode($text, true, 128, JSON_THROW_ON_ERROR | JSON_BIGINT_AS_STRING); }
        catch (\Throwable $e) { throw new \RuntimeException('wechat_invalid_response'); }
        if (!is_array($data)) throw new \RuntimeException('wechat_invalid_response');
        return $data;
    }
    public static function info(): array { return ['channel_version' => '2.4.10', 'bot_agent' => 'FusanheCRM/1.0.0']; }
    /** Only known error categories and numeric codes leave the private API response. */
    public static function rejection(array $response): array
    {
        $code = null;
        foreach (['errcode','ret'] as $field) {
            $value = $response[$field] ?? null;
            if ((is_int($value) || is_string($value) && preg_match('/^-?\d{1,10}$/D', $value)) && (int) $value !== 0) { $code = (int) $value; break; }
        }
        $message = strtolower((string) ($response['errmsg'] ?? $response['message'] ?? ''));
        $context = str_contains($message, 'context') && preg_match('/expir|invalid|timeout|not.*valid/', $message);
        return ['error' => $code === -14 ? 'report_token_expired' : ($context ? 'report_context_expired' : 'report_rejected'), 'providerCode' => $code];
    }
    /** Tencent 2.4.10 SendMessageResp has optional ret and a uint64 message_id. */
    public static function acknowledgement(array $response): ?bool
    {
        foreach (['ret', 'errcode'] as $field) {
            if (!array_key_exists($field, $response)) continue;
            $value = $response[$field];
            if (!(is_int($value) || (is_string($value) && preg_match('/^-?\d+$/D', $value)))) return null;
            if ((int) $value !== 0) return false;
        }
        if (array_key_exists('ret', $response)) return true;
        $id = $response['message_id'] ?? null;
        if (!(is_int($id) || is_string($id))) return null;
        $id = (string) $id;
        return preg_match('/^[1-9]\d{0,19}$/D', $id) && (strlen($id) < 20 || strcmp($id, '18446744073709551615') <= 0) ? true : null;
    }
}
