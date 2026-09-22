<?php
namespace Espo\Custom\Tools\Fusanhe\Api;

use Espo\Core\Api\Action;
use Espo\Core\Api\Request;
use Espo\Core\Api\Response;
use Espo\Core\Api\ResponseComposer;
use Espo\Core\Exceptions\BadRequest;
use Espo\Custom\Tools\Fusanhe\AutomationAuth;
use Espo\Custom\Tools\Fusanhe\WorkflowService;
use stdClass;

final class PostAgentHeartbeat implements Action
{
    public function __construct(
        private WorkflowService $service,
        private AutomationAuth $auth,
    ) {}

    public function process(Request $request): Response
    {
        $body = $request->getParsedBody();
        if (!($body instanceof \stdClass)) {
            throw new BadRequest('JSON object body is required.');
        }
        $agentKey = (string) ($body->agentKey ?? '');
        $agent = $this->auth->assertAgent($request, $agentKey);
        $body->agentKey = (string) $agent->get('agentKey');

        return ResponseComposer::json($this->service->heartbeat($body));
    }
}
