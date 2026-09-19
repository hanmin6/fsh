<?php
namespace Espo\Custom\Tools\Fusanhe\Api;

use Espo\Core\Api\Action;
use Espo\Core\Api\Request;
use Espo\Core\Api\Response;
use Espo\Core\Api\ResponseComposer;
use Espo\Core\Acl;
use Espo\Core\Exceptions\BadRequest;
use Espo\Core\Exceptions\Forbidden;
use Espo\Entities\User;
use Espo\ORM\EntityManager;
use Espo\Custom\Tools\Fusanhe\WorkflowService;

final class PostGenerateDraft extends AbstractFusanheAction
{
    public function __construct(
        private WorkflowService $service,
        User $user,
        Acl $acl,
        EntityManager $em
    ) {
        parent::__construct($user, $acl, $em);
    }

    public function process(Request $request): Response
    {
        if (!$this->user->isAdmin() && !$this->acl->checkScope('AIReplyDraft', 'create')) {
            throw new Forbidden('Not allowed to create drafts.');
        }
        $id = $request->getRouteParam('id');
        if (!$id) {
            throw new BadRequest();
        }
        $this->requireEntityScope('ExternalConversation', $id, 'read');
        return ResponseComposer::json($this->service->generateDraft($id, $this->user));
    }
}
