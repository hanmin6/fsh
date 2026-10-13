<?php
namespace Espo\Custom\Tools\Fusanhe;

/** Acquisition ownership policy. Rating does not itself grant permission to send. */
final class AcquisitionRouting
{
    public const FIELDS = ['rating', 'ratingSource', 'aiRating', 'aiRatingStatus', 'fusanheContactPolicy', 'fusanheDoNotContact', 'fusanheSourceSystem', 'fusanheSourceId'];

    public static function effectiveRating(array $customer): string
    {
        $rating = (string) ($customer['rating'] ?? '');
        if (in_array($rating, ['S', 'A', 'B', 'C', 'D'], true)) return $rating;
        // An explicit manual clear is authoritative, including over an older AI result.
        if (($customer['ratingSource'] ?? '') === 'manual') return '';
        $automatic = (string) ($customer['aiRating'] ?? '');
        return ($customer['aiRatingStatus'] ?? '') === 'completed' && in_array($automatic, ['S', 'A', 'B', 'C', 'D'], true) ? $automatic : '';
    }

    public static function route(array $customer): string
    {
        if (!empty($customer['fusanheDoNotContact']) || in_array($customer['fusanheContactPolicy'] ?? '', ['optedOut', 'restricted'], true)) return 'blocked';
        return match (self::effectiveRating($customer)) {
            'S', 'A' => 'human',
            'B', 'C', 'D' => 'ai',
            default => 'pending_rating',
        };
    }

    public static function isAcquisition(array $customer): bool
    {
        return in_array(strtolower(trim((string) ($customer['fusanheSourceSystem'] ?? ''))), ['muse', 'xpoz', 'openoutreach'], true)
            && trim((string) ($customer['fusanheSourceId'] ?? '')) !== '';
    }

    public static function reason(array $customer): string
    {
        return match (self::route($customer)) {
            'blocked' => '客户拒绝联系或联系策略受限，停止自动触达。',
            'human' => '高价值客户（S/A），由人工洽谈。',
            'ai' => '中低价值客户（B/C/D），由 AI 跟进；实际发送仍需可用渠道。',
            default => '客户价值尚未确定，先完成评级。',
        };
    }
}
