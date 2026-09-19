<?php
namespace Espo\Custom\Tools\Fusanhe;

/**
 * Feature flags hide industry modules by default (nav + API). They are NOT a
 * permission mechanism: scope ACLs and workflow rules are always enforced.
 */
final class Features
{
    public const MAP = [
        'products' => 'FUSANHE_FEATURE_PRODUCTS',
        'certificates' => 'FUSANHE_FEATURE_CERTIFICATES',
        'samples' => 'FUSANHE_FEATURE_SAMPLES',
        'quotes' => 'FUSANHE_FEATURE_QUOTES',
        'orders' => 'FUSANHE_FEATURE_ORDERS',
    ];

    public static function enabled(string $feature): bool
    {
        $var = self::MAP[$feature] ?? null;
        if ($var === null) return false;
        return filter_var(getenv($var) ?: '', FILTER_VALIDATE_BOOLEAN);
    }

    /** @return array<string, bool> */
    public static function all(): array
    {
        $out = [];
        foreach (self::MAP as $feature => $var) {
            $out[$feature] = self::enabled($feature);
        }
        return $out;
    }
}
