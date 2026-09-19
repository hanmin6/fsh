<?php
namespace Espo\Custom\Tools\Fusanhe\Api;

use Espo\Core\Api\Action;
use Espo\Core\Api\Request;
use Espo\Core\Api\Response;
use Espo\Core\Api\ResponseComposer;
use Espo\Core\Acl;
use Espo\Core\Exceptions\Forbidden;
use Espo\Custom\Tools\Fusanhe\WorkflowService;

final class GetStatus implements Action
{
    public function __construct(
        private WorkflowService $service,
        private Acl $acl,
    ) {}

    public function process(Request $request): Response
    {
        if (!$this->acl->checkScope('ExternalConversation', 'read')) {
            throw new Forbidden('Not allowed to read conversation status.');
        }
        return ResponseComposer::json($this->service->status());
    }
}
