<?php
namespace Espo\Custom\Tools\Fusanhe\Api;

use Espo\Core\Api\Action;
use Espo\Core\Api\Request;
use Espo\Core\Api\Response;
use Espo\Core\Api\ResponseComposer;
use Espo\Core\Acl;
use Espo\Core\Exceptions\Forbidden;
use Espo\Custom\Tools\Fusanhe\WorkflowService;

/** Mock/demo intake is no longer a wide-open endpoint: it writes conversations. */
final class PostMockIntake implements Action
{
    public function __construct(
        private WorkflowService $service,
        private Acl $acl,
    ) {}

    public function process(Request $request): Response
    {
        if (!$this->acl->checkScope('ExternalConversation', 'create')) {
            throw new Forbidden('Not allowed to import inquiries.');
        }
        return ResponseComposer::json($this->service->intake($request->getParsedBody()));
    }
}
