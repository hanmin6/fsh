<?php
namespace Espo\Custom\Tools\Fusanhe\Api;

final class RequestContext
{
    private static ?string $requestId = null;

    public static function set(string $requestId): void
    {
        self::$requestId = $requestId;
    }

    public static function requestId(): ?string
    {
        return self::$requestId;
    }

    public static function clear(): void
    {
        self::$requestId = null;
    }
}
