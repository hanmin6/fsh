<?php
namespace Espo\Custom\Tools\Fusanhe\Api;

use Espo\Core\Api\Action;
use Espo\Core\Api\Request;
use Espo\Core\Api\Response;
use Espo\Core\Api\ResponseComposer;
use Espo\Core\Exceptions\BadRequest;
use Espo\Custom\Tools\Fusanhe\AutomationAuth;
use Espo\Custom\Tools\Fusanhe\MadeInChinaSyncService;

final class PostMadeInChinaSync implements Action
{
    public function __construct(
        private MadeInChinaSyncService $service,
        private AutomationAuth $auth,
    ) {}

    public function process(Request $request): Response
    {
        $agent = $this->auth->assertAgent($request);
        try {
            $body = $request->getParsedBody();
        } catch (\Throwable $e) {
            throw new BadRequest('Malformed JSON body: ' . $e->getMessage());
        }
        if (!($body instanceof \stdClass)) {
            throw new BadRequest('JSON object body is required.');
        }

        return ResponseComposer::json($this->service->sync($body, $agent));
    }
}
