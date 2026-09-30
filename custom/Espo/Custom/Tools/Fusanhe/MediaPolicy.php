<?php
namespace Espo\Custom\Tools\Fusanhe;

use Espo\Core\Exceptions\BadRequest;

final class MediaPolicy
{
    public const ACTIVE = ['submitting', 'queued', 'processing', 'reconcile_required'];
    public const TERMINAL = ['completed', 'failed'];

    public static function key(mixed $key): string
    {
        if (!is_string($key) || !preg_match('/^[A-Za-z0-9][A-Za-z0-9._-]{15,79}$/D', $key)) {
            throw new BadRequest('A stable idempotencyKey of 16–80 characters is required.');
        }
        return $key;
    }

    public static function preferences(object $input): array
    {
        $values = ['purpose' => (string) ($input->purpose ?? '产品介绍'), 'language' => (string) ($input->language ?? '英语'),
            'aspect' => (string) ($input->aspect ?? '16:9'), 'duration' => (string) ($input->duration ?? '5')];
        foreach (['purpose' => ['产品介绍', '客户沟通', '社交宣传'], 'language' => ['英语', '中文', '西班牙语'],
            'aspect' => ['16:9', '9:16', '1:1'], 'duration' => ['5', '10']] as $key => $allowed) {
            if (!in_array($values[$key], $allowed, true)) throw new BadRequest('Invalid creative preferences.');
        }
        return $values;
    }

    public static function image(string $dataUrl): array
    {
        if (strlen($dataUrl) > 2800000 || !preg_match('#^data:(image/(?:png|jpeg|webp));base64,([A-Za-z0-9+/=]+)$#D', $dataUrl, $m)) {
            throw new BadRequest('Choose a PNG, JPEG or WebP image of at most 2 MB.');
        }
        $bytes = base64_decode($m[2], true);
        if ($bytes === false || strlen($bytes) > 2 * 1024 * 1024 || strlen($bytes) < 12) throw new BadRequest('Invalid image.');
        $info = @getimagesizefromstring($bytes);
        if (!$info || ($info['mime'] ?? '') !== $m[1] || $info[0] > 10000 || $info[1] > 10000 || $info[0] * $info[1] > 25000000) {
            throw new BadRequest('Invalid image or excessive image dimensions.');
        }
        return ['bytes' => $bytes, 'mime' => $m[1], 'size' => strlen($bytes), 'sha256' => hash('sha256', $bytes)];
    }

    public static function plans(string $content): array
    {
        try { $value = json_decode($content, true, 16, JSON_THROW_ON_ERROR); }
        catch (\Throwable) { throw new \RuntimeException('creative_invalid_response'); }
        if (!is_array($value['plans'] ?? null) || count($value['plans']) !== 3) throw new \RuntimeException('creative_invalid_response');
        $plans = [];
        foreach ($value['plans'] as $plan) {
            $row = [];
            foreach (['name' => 80, 'description' => 400, 'motion' => 1000, 'use' => 100] as $key => $max) {
                if (!is_string($plan[$key] ?? null) || trim($plan[$key]) === '' || strlen($plan[$key]) > $max * 4) {
                    throw new \RuntimeException('creative_invalid_response');
                }
                $row[$key] = trim($plan[$key]);
            }
            $plans[] = $row;
        }
        return $plans;
    }

    public static function transition(string $from, string $to): void
    {
        $allowed = ['submitting' => ['queued', 'processing', 'completed', 'failed', 'reconcile_required'],
            'queued' => ['queued', 'processing', 'completed', 'failed', 'reconcile_required'],
            'processing' => ['processing', 'completed', 'failed', 'reconcile_required'],
            'reconcile_required' => ['queued', 'processing', 'completed', 'failed', 'reconcile_required']];
        if (!in_array($to, $allowed[$from] ?? [], true)) throw new \RuntimeException('media_invalid_transition');
    }
}
