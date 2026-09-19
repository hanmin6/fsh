<?php
namespace Espo\Custom\Tools\Fusanhe;

/**
 * Request-scoped marker for saves performed by Fusanhe workflow services.
 * Hooks use it to tell controlled service writes apart from generic REST CRUD,
 * which must not bypass approval, snapshot or state-machine rules.
 *
 * The counter makes the marker exception-safe and nesting-aware: `clear`
 * only releases the caller's own level, and `wrap` guarantees release even
 * when the callback throws (relevant under long-lived worker processes).
 */
final class InternalWrite
{
    private static int $depth = 0;

    public static function flag(): void
    {
        self::$depth++;
    }

    public static function clear(): void
    {
        if (self::$depth > 0) {
            self::$depth--;
        }
    }

    public static function isFlagged(): bool
    {
        return self::$depth > 0;
    }

    /** Run a callback as an internal write, releasing the marker afterwards. */
    public static function wrap(callable $fn)
    {
        self::flag();
        try {
            return $fn();
        } finally {
            self::clear();
        }
    }
}
