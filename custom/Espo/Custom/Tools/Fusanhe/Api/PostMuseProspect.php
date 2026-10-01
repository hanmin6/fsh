<?php

namespace Espo\Custom\Tools\Fusanhe\Api;

use Espo\Core\Api\Action;
use Espo\Core\Api\Request;
use Espo\Core\Api\Response;
use Espo\Core\Api\ResponseComposer;
use Espo\Core\Exceptions\BadRequest;
use Espo\Custom\Tools\Fusanhe\AutomationAuth;
use Espo\Custom\Tools\Fusanhe\MuseCrmService;
use Espo\Custom\Tools\Fusanhe\Api\RequestContext;

final class PostMuseProspect implements Action
{
    public function __construct(
        private MuseCrmService $service,
        private AutomationAuth $auth,
    ) {}

    public function process(Request $request): Response
    {
        $agent = $this->auth->assertAgent($request);
        $body = $request->getParsedBody();
        if (!($body instanceof \stdClass)) {
            throw new BadRequest('JSON object body is required.');
        }
        return ResponseComposer::json(['requestId' => RequestContext::requestId()] + $this->service->upsertProspect($body, $agent));
    }
}
