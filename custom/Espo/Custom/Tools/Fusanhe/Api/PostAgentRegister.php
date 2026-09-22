<?php
namespace Espo\Custom\Tools\Fusanhe\Api;

use Espo\Core\Api\Action;
use Espo\Core\Api\Request;
use Espo\Core\Api\Response;
use Espo\Core\Api\ResponseComposer;
use Espo\Core\Exceptions\BadRequest;
use Espo\Custom\Tools\Fusanhe\AutomationAuth;
use Espo\Custom\Tools\Fusanhe\WorkflowService;

final class PostAgentRegister implements Action
{
    public function __construct(
        private WorkflowService $service,
        private AutomationAuth $auth,
    ) {}

    public function process(Request $request): Response
    {
        $this->auth->assertBootstrap($request);
        $body = $request->getParsedBody();
        if (!($body instanceof \stdClass)) {
            throw new BadRequest('JSON object body is required.');
        }

        return ResponseComposer::json($this->service->registerAgent($body));
    }
}
