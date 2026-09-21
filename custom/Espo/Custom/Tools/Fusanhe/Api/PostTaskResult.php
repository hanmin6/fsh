<?php
namespace Espo\Custom\Tools\Fusanhe\Api;

use Espo\Core\Api\Action;
use Espo\Core\Api\Request;
use Espo\Core\Api\Response;
use Espo\Core\Api\ResponseComposer;
use Espo\Custom\Tools\Fusanhe\WorkflowService;use Espo\Custom\Tools\Fusanhe\AutomationAuth;use Espo\Core\Exceptions\BadRequest;
final class PostTaskResult implements Action
{
    public function __construct(private WorkflowService $service, private AutomationAuth $auth) {}
    public function process(Request $request): Response
    {
        $body = $request->getParsedBody();
        $this->auth->assertAgent($request, (string) ($body->agentKey ?? ''));
        $id = $request->getRouteParam('id');
        if (!$id) throw new BadRequest('Task id is required.');
        return ResponseComposer::json($this->service->reportResult($id, $body));
    }
}
