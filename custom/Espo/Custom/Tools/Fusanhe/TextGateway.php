<?php
namespace Espo\Custom\Tools\Fusanhe;

/** Isolated OpenAI-compatible text channel. No automatic retries or model substitutions. */
final class TextGateway
{
    private const CHOICES = ['gpt' => 'GPT-6.1 Sol', 'grok' => 'Grok 4.7', 'gemini' => 'Gemini 3.8 Flash'];

    /** Injectable transport is for offline contracts; production always uses verified TLS. */
    public function __construct(private ?\Closure $transport = null) {}

    public static function usesNewChannel(): bool
    {
        return filter_var(getenv('FUSANHE_TEXT_ENABLED') ?: 'false', FILTER_VALIDATE_BOOLEAN)
            || (string) getenv('FUSANHE_TEXT_API_KEY') !== '';
    }

    public function status(): array
    {
        $new = self::usesNewChannel();
        $key = (string) getenv($new ? 'FUSANHE_TEXT_API_KEY' : 'AI_API_KEY');
        $base = (string) (getenv($new ? 'FUSANHE_TEXT_API_BASE_URL' : 'AI_API_BASE_URL') ?: ($new ? '' : 'https://api.openai.com/v1'));
        $default = $new ? (string) (getenv('FUSANHE_TEXT_DEFAULT_MODEL') ?: 'gpt') : 'legacy';
        $configured = $key !== '' && self::validBase($base);
        $models = [];
        foreach ($new ? self::CHOICES : ['legacy' => '原有文本模型'] as $choice => $label) {
            $id = (string) ($new ? getenv('FUSANHE_TEXT_MODEL_' . strtoupper($choice)) : (getenv('AI_MODEL') ?: 'gpt-4.1-mini'));
            $models[] = ['choice' => $choice, 'label' => $label, 'model' => $id ?: null, 'available' => $configured && $id !== ''];
        }
        $available = array_values(array_filter($models, fn ($m) => $m['choice'] === $default && $m['available']));
        return ['provider' => $new ? 'apimonth' : 'openai-compatible', 'configured' => $configured,
            'available' => (bool) $available, 'defaultChoice' => $default, 'models' => $models,
            'status' => $available ? 'configured' : 'unavailable', 'healthChecked' => false,
            'cost' => 'unknown'];
    }

    /** Changes to endpoint/model/default invalidate privacy-preserving analysis caches. */
    public function fingerprint(): string
    {
        $status = $this->status();
        $prefix = self::usesNewChannel() ? 'FUSANHE_TEXT_' : 'AI_';
        return hash('sha256', json_encode([$status, (string) getenv($prefix . 'API_BASE_URL')]));
    }

    public function complete(array $messages, ?string $choice = null, bool $json = true): array
    {
        $status = $this->status();
        $choice ??= $status['defaultChoice'];
        $selected = array_values(array_filter($status['models'], fn ($m) => $m['choice'] === $choice));
        if (!$selected) throw new \RuntimeException('text_invalid_choice');
        if (!$selected[0]['available']) throw new \RuntimeException('text_not_configured');
        if (!$messages || !array_is_list($messages) || count($messages) > 30) throw new \RuntimeException('text_invalid_messages');
        $size = 0;
        foreach ($messages as $message) {
            if (!is_array($message) || !in_array($message['role'] ?? '', ['system', 'user', 'assistant'], true) || !is_string($message['content'] ?? null)) throw new \RuntimeException('text_invalid_messages');
            $size += strlen($message['content']);
        }
        if ($size > 65536) throw new \RuntimeException('text_input_too_large');
        $prefix = self::usesNewChannel() ? 'FUSANHE_TEXT_' : 'AI_';
        $base = rtrim((string) (getenv($prefix . 'API_BASE_URL') ?: 'https://api.openai.com/v1'), '/');
        $key = (string) getenv($prefix . 'API_KEY');
        $responses = self::usesNewChannel() && $choice === 'gpt';
        $endpoint = $base . ($responses ? '/responses' : '/chat/completions');
        $payload = $responses
            ? ['model' => $selected[0]['model'], 'input' => $messages, 'max_output_tokens' => 1600, 'stream' => false, 'store' => false]
            : ['model' => $selected[0]['model'], 'messages' => $messages, 'max_tokens' => 1600];
        if ($json) {
            if ($responses) $payload['text'] = ['format' => ['type' => 'json_object']];
            else $payload['response_format'] = ['type' => 'json_object'];
        }
        $timeout = max(5, min(90, (int) (getenv($prefix . 'TIMEOUT') ?: 45)));
        try {
            [$code, $raw] = $this->transport
                ? ($this->transport)($endpoint, $payload, $key, $timeout)
                : $this->request($endpoint, $payload, $key, $timeout);
        } catch (\Throwable $e) {
            throw new \RuntimeException('text_transport_failed');
        }
        if ($code === 401 || $code === 403) throw new \RuntimeException('text_auth_failed');
        if ($code === 429) throw new \RuntimeException('text_rate_limited');
        if (!is_string($raw) || $code < 200 || $code >= 300) throw new \RuntimeException('text_transport_failed');
        if (strlen($raw) > 262144) throw new \RuntimeException('text_response_too_large');
        $out = json_decode($raw, true);
        $content = $out['choices'][0]['message']['content'] ?? null;
        if ($responses) {
            if (($out['status'] ?? '') !== 'completed') throw new \RuntimeException('text_incomplete_response');
            $parts = [];
            foreach ($out['output'] ?? [] as $item) {
                foreach ($item['content'] ?? [] as $block) {
                    if (($block['type'] ?? '') === 'output_text' && is_string($block['text'] ?? null)) $parts[] = $block['text'];
                }
            }
            $content = implode('', $parts);
        } else if (($out['choices'][0]['finish_reason'] ?? 'stop') !== 'stop') {
            throw new \RuntimeException('text_incomplete_response');
        }
        if (!is_string($content) || trim($content) === '') throw new \RuntimeException('text_invalid_response');
        if ($json && !is_array(json_decode($content, true))) throw new \RuntimeException('text_invalid_json');
        $model = $out['model'] ?? (self::usesNewChannel() ? null : $selected[0]['model']);
        if (!is_string($model) || $model === '' || strlen($model) > 100 || !preg_match('/^[A-Za-z0-9._:\/\-]+$/D', $model)) throw new \RuntimeException('text_invalid_response');
        // Provider catalogs and protocol smokes confirmed exact IDs. Any different
        // upstream ID must be reviewed explicitly before accepting its provenance.
        if (self::usesNewChannel() && $model !== $selected[0]['model']) throw new \RuntimeException('text_model_mismatch');
        $usage = $out['usage']['total_tokens'] ?? null;
        return ['content' => $content, 'provider' => $status['provider'], 'model' => $model,
            'requestedModel' => $selected[0]['model'], 'usageTokens' => is_numeric($usage) ? max(0, (int) $usage) : null];
    }

    private static function validBase(string $base): bool
    {
        $parts = parse_url($base);
        return $parts && ($parts['scheme'] ?? '') === 'https' && !empty($parts['host'])
            && !isset($parts['pass']) && !isset($parts['user'])
            && !isset($parts['query']) && !isset($parts['fragment']);
    }

    private function request(string $url, array $payload, string $key, int $timeout): array
    {
        $ch = curl_init($url);
        $raw = ''; $tooLarge = false;
        curl_setopt_array($ch, [CURLOPT_POST => true, CURLOPT_HTTPHEADER => ['Authorization: Bearer ' . $key, 'Content-Type: application/json'],
            CURLOPT_POSTFIELDS => json_encode($payload, JSON_THROW_ON_ERROR), CURLOPT_TIMEOUT => $timeout,
            CURLOPT_CONNECTTIMEOUT => 10, CURLOPT_FOLLOWLOCATION => false, CURLOPT_SSL_VERIFYPEER => true,
            CURLOPT_SSL_VERIFYHOST => 2, CURLOPT_PROTOCOLS => CURLPROTO_HTTPS,
            CURLOPT_WRITEFUNCTION => static function ($handle, string $chunk) use (&$raw, &$tooLarge): int {
                if (strlen($raw) + strlen($chunk) > 262144) { $tooLarge = true; return 0; }
                $raw .= $chunk; return strlen($chunk);
            }]);
        $ok = curl_exec($ch); $code = (int) curl_getinfo($ch, CURLINFO_RESPONSE_CODE); curl_close($ch);
        if ($tooLarge) return [200, str_repeat(' ', 262145)];
        return [$code, $ok === false ? false : $raw];
    }
}
