<?php
namespace Espo\Custom\Tools\Fusanhe;

use Espo\Core\Api\Request;
use Espo\Core\Exceptions\Forbidden;

final class AutomationAuth
{
    public function assert(Request $request): void
    {
        $expected = (string) getenv('FUSANHE_AUTOMATION_TOKEN');
        $actual = (string) ($request->getHeader('X-Automation-Token') ?? '');
        if ($expected === '' || $expected === 'replace-with-a-long-random-token' || !hash_equals($expected, $actual)) {
            throw new Forbidden('Invalid automation token.');
        }
    }
}
