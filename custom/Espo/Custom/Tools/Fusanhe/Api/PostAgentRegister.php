<?php
namespace Espo\Custom\Tools\Fusanhe\Api;

use Espo\Core\Api\Action;
use Espo\Core\Api\Request;
use Espo\Core\Api\Response;
use Espo\Core\Api\ResponseComposer;
use Espo\Custom\Tools\Fusanhe\WorkflowService;use Espo\Custom\Tools\Fusanhe\AutomationAuth;
final class PostAgentRegister implements Action
{
    public function __construct(private WorkflowService $service, private AutomationAuth $auth) {}

    public function process(Request $request): Response
    {
        $this->auth->assertBootstrap($request);
        $body = $request->getParsedBody();
        $result = $this->service->registerAgent($body);
        return ResponseComposer::json($result + $this->auth->issueCredential((string) ($body->agentKey ?? '')));
    }
}
