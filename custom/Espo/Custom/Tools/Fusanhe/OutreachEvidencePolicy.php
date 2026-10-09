<?php
namespace Espo\Custom\Tools\Fusanhe;

use Espo\Core\Exceptions\BadRequest;

/** Validation and redaction rules for CRM-side outreach evidence. */
final class OutreachEvidencePolicy
{
    public const VERSION = 'outreach-research-v1';
    public const CHANNELS = ['LinkedIn', 'Facebook', 'Instagram', 'TikTok', 'X', 'Alibaba', 'MadeInChina', 'Email', 'WhatsApp', 'Other'];
    public const STATUSES = ['sent', 'delivered', 'uncertain', 'failed', 'mockSent'];
    public const TARGETS = ['Lead', 'Account', 'Contact'];
    private const MAX_IMAGE_BYTES = 4 * 1024 * 1024;
    private const MAX_MESSAGE_BYTES = 20000;

    public static function idempotency(mixed $value): string
    {
        if (!is_string($value) || !preg_match('/^[A-Za-z0-9][A-Za-z0-9._:-]{15,79}$/D', $value)) {
            throw new BadRequest('A stable idempotencyKey of 16-80 characters is required.');
        }
        return $value;
    }

    public static function targetType(mixed $value): string
    {
        $value = is_string($value) ? trim($value) : '';
        if (!in_array($value, self::TARGETS, true)) throw new BadRequest('A valid targetType is required.');
        return $value;
    }

    public static function targetId(mixed $value): string
    {
        $value = is_string($value) ? trim($value) : '';
        if ($value === '' || strlen($value) > 24 || !preg_match('/^[A-Za-z0-9]+$/D', $value)) throw new BadRequest('A valid targetId is required.');
        return $value;
    }

    public static function screenshot(mixed $value): array
    {
        if (!is_string($value) || strlen($value) > 5800000 || !preg_match('#^data:(image/(?:png|jpeg|webp));base64,([A-Za-z0-9+/=]+)$#D', $value, $match)) {
            throw new BadRequest('A PNG, JPEG or WebP screenshot of at most 4 MiB is required.');
        }
        $bytes = base64_decode($match[2], true);
        if ($bytes === false || strlen($bytes) < 32 || strlen($bytes) > self::MAX_IMAGE_BYTES) throw new BadRequest('Invalid screenshot size.');
        $info = @getimagesizefromstring($bytes);
        if (!$info || ($info['mime'] ?? '') !== $match[1] || ($info[0] ?? 0) > 10000 || ($info[1] ?? 0) > 10000 || ($info[0] ?? 0) * ($info[1] ?? 0) > 25000000) {
            throw new BadRequest('Invalid screenshot dimensions or MIME type.');
        }
        return ['bytes' => $bytes, 'mime' => $match[1], 'size' => strlen($bytes), 'sha256' => hash('sha256', $bytes), 'width' => (int) $info[0], 'height' => (int) $info[1]];
    }

    public static function message(mixed $value): string
    {
        if (!is_string($value) || trim($value) === '' || strlen($value) > self::MAX_MESSAGE_BYTES) throw new BadRequest('messageBody is required and bounded.');
        return trim($value);
    }

    public static function url(mixed $value, int $max = 255): string
    {
        $value = is_string($value) ? trim($value) : '';
        if ($value === '') return '';
        if (strlen($value) > $max || !filter_var($value, FILTER_VALIDATE_URL) || !in_array(parse_url($value, PHP_URL_SCHEME), ['http', 'https'], true)) throw new BadRequest('Invalid public profile URL.');
        if (parse_url($value, PHP_URL_USER) !== null || parse_url($value, PHP_URL_PASS) !== null) throw new BadRequest('URL credentials are not allowed.');
        return $value;
    }

    public static function sentAt(mixed $value): string
    {
        $value = is_string($value) ? trim($value) : '';
        if (!preg_match('/^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:Z|[+-]\d{2}:\d{2})$/D', $value)) throw new BadRequest('An absolute sentAt timestamp is required.');
        try { $at = new \DateTimeImmutable($value, new \DateTimeZone('UTC')); }
        catch (\Throwable) { throw new BadRequest('Invalid sentAt.'); }
        if (\DateTimeImmutable::getLastErrors() !== false) throw new BadRequest('Invalid sentAt.');
        if ($at > (new \DateTimeImmutable('now', new \DateTimeZone('UTC')))->modify('+10 minutes')) throw new BadRequest('sentAt cannot be in the future.');
        return $at->setTimezone(new \DateTimeZone('UTC'))->format('Y-m-d H:i:s');
    }

    public static function customerSnapshot(mixed $value): array
    {
        if ($value === null || $value === '') return [];
        if (is_object($value)) $value = get_object_vars($value);
        if (!is_array($value) || count($value) > 20) throw new BadRequest('customerSnapshot must be a bounded object.');
        $allowed = ['name', 'company', 'role', 'country', 'website', 'profileUrl', 'source', 'publicBio', 'publicTags'];
        $out = [];
        foreach ($allowed as $key) {
            if (!array_key_exists($key, $value)) continue;
            $item = $value[$key];
            if (is_array($item)) {
                if (count($item) > 20 || count(array_filter($item, 'is_string')) !== count($item)) throw new BadRequest('Invalid public tags.');
                $item = implode(', ', $item);
            }
            if (!is_string($item)) throw new BadRequest('customerSnapshot fields must be strings.');
            if (in_array($key, ['website', 'profileUrl'], true)) $item = self::url($item);
            $item = self::redactContactData(trim($item));
            $out[$key] = mb_substr($item, 0, $key === 'publicBio' ? 4000 : 500);
        }
        if (strlen(json_encode($out, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES)) > 12000) throw new BadRequest('customerSnapshot is too large.');
        ksort($out);
        return $out;
    }

    public static function status(mixed $value): string
    {
        $value = is_string($value) ? trim($value) : 'uncertain';
        if (!in_array($value, self::STATUSES, true)) throw new BadRequest('Unsupported sendStatus.');
        return $value;
    }

    public static function channel(mixed $value): string
    {
        $value = is_string($value) ? trim($value) : '';
        if (!in_array($value, self::CHANNELS, true)) throw new BadRequest('Unsupported channelType.');
        return $value;
    }

    public static function safeResearchInput(array $snapshot, string $profileUrl, string $message): array
    {
        $message = preg_replace('/[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/i', '[email]', $message) ?? '';
        $message = preg_replace('/\+?\d[\d\s().-]{7,}\d/', '[phone]', $message) ?? '';
        foreach ($snapshot as &$field) {
            $field = preg_replace('/[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/i', '[email]', $field) ?? '';
            $field = preg_replace('/\+?\d[\d\s().-]{7,}\d/', '[phone]', $field) ?? '';
        }
        unset($field);
        return ['customer' => $snapshot, 'profileUrl' => $profileUrl, 'messageContext' => mb_substr($message, 0, 2000)];
    }

    private static function redactContactData(string $value): string
    {
        $value = preg_replace('/[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/i', '[email]', $value) ?? '';
        return preg_replace('/\+?\d[\d\s().-]{7,}\d/', '[phone]', $value) ?? '';
    }
}
