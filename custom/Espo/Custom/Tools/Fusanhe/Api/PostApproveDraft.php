<?php
namespace Espo\Custom\Tools\Fusanhe\Api;

use Espo\Core\Api\Action;
use Espo\Core\Api\Request;
use Espo\Core\Api\Response;
use Espo\Core\Api\ResponseComposer;
use Espo\Custom\Tools\Fusanhe\WorkflowService;
use Espo\Core\Exceptions\BadRequest;
use Espo\Entities\User;
use Espo\Core\Acl;
use Espo\Core\Exceptions\Forbidden;
use Espo\Core\Exceptions\NotFound;
final class PostApproveDraft implements Action
{
    public function __construct(private WorkflowService $service, private User $user, private Acl $acl, private \Espo\ORM\EntityManager $em) {}

    public function process(Request $request): Response
    {
        if (!$this->user->isAdmin() && !$this->acl->checkScope('OutboundTask', 'create')) {
            throw new Forbidden('Not allowed to approve outbound messages.');
        }
        $id = $request->getRouteParam('id');
        if (!$id) throw new BadRequest();
        $b = $request->getParsedBody();
        // Row-level check: the approver must be able to read the draft and its conversation.
        $draft = $this->em->getEntityById('AIReplyDraft', $id);
        if (!$draft) throw new NotFound('AIReplyDraft not found.');
        if (!$this->user->isAdmin() && !$this->acl->checkEntity($draft, 'read')) {
            throw new Forbidden('Not allowed to read this draft.');
        }
        $conversation = $this->em->getEntityById('ExternalConversation', (string) $draft->get('conversationId'));
        if ($conversation && !$this->user->isAdmin() && !$this->acl->checkEntity($conversation, 'read')) {
            throw new Forbidden('Not allowed to read this conversation.');
        }
        return ResponseComposer::json($this->service->approve($id, $this->user, isset($b->draftText) ? (string) $b->draftText : null));
    }
}
