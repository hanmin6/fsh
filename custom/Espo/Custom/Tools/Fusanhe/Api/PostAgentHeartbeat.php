<?php
namespace Espo\Custom\Tools\Fusanhe\Api;

use Espo\Core\Api\Action;
use Espo\Core\Api\Request;
use Espo\Core\Api\Response;
use Espo\Core\Api\ResponseComposer;
use Espo\Custom\Tools\Fusanhe\WorkflowService;use Espo\Custom\Tools\Fusanhe\AutomationAuth;
final class PostAgentHeartbeat implements Action { public function __construct(private WorkflowService $service,private AutomationAuth $auth) {} public function process(Request $request): Response {$this->auth->assert($request);return ResponseComposer::json($this->service->heartbeat($request->getParsedBody()));} }
