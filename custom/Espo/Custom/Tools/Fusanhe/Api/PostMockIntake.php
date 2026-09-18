<?php
namespace Espo\Custom\Tools\Fusanhe\Api;

use Espo\Core\Api\Action;
use Espo\Core\Api\Request;
use Espo\Core\Api\Response;
use Espo\Core\Api\ResponseComposer;
use Espo\Custom\Tools\Fusanhe\WorkflowService;
final class PostMockIntake implements Action { public function __construct(private WorkflowService $service) {} public function process(Request $request): Response { return ResponseComposer::json($this->service->intake($request->getParsedBody())); } }
