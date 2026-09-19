<?php
namespace Espo\Custom\Tools\Fusanhe\Api;

use Espo\Core\Api\Action;
use Espo\Core\Api\Request;
use Espo\Core\Api\Response;
use Espo\Core\Api\ResponseComposer;
use Espo\Core\Acl;
use Espo\Core\Exceptions\BadRequest;
use Espo\Core\Exceptions\Forbidden;
use Espo\Custom\Tools\Fusanhe\WorkflowService;
use Espo\Entities\User;

final class PostGenerateDraft implements Action
{
    public function __construct(
        private WorkflowService $service,
        private User $user,
        private Acl $acl,
    ) {}

    public function process(Request $request): Response
    {
        if (!$this->acl->checkScope('AIReplyDraft', 'create')) {
            throw new Forbidden('Not allowed to create drafts.');
        }
        $id = $request->getRouteParam('id');
        if (!$id) {
            throw new BadRequest();
        }
        return ResponseComposer::json($this->service->generateDraft($id, $this->user));
    }
}
