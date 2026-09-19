<?php
namespace Espo\Custom\Tools\Fusanhe\Api;

use Espo\Core\Api\Action;
use Espo\Core\Api\Request;
use Espo\Core\Api\Response;
use Espo\Core\Api\ResponseComposer;
use Espo\Core\Exceptions\Forbidden;
use Espo\Entities\User;
use Espo\ORM\EntityManager;
use Espo\Core\Acl;
use Espo\Custom\Tools\Fusanhe\WorkflowService;

/**
 * Read-only aggregates. Users whose read level is not "all" only see their
 * own numbers instead of org-wide metrics.
 */
final class GetDashboard extends AbstractFusanheAction
{
    public function __construct(
        User $user,
        Acl $acl,
        EntityManager $em,
        private WorkflowService $service
    ) {
        parent::__construct($user, $acl, $em);
    }

    public function process(Request $request): Response
    {
        if (!$this->user->isAdmin() && !$this->acl->checkScope('ExternalConversation', 'read')) {
            throw new Forbidden('Not allowed to read the dashboard.');
        }
        $ownUserId = null;
        if (!$this->user->isAdmin() && $this->acl->getLevel('ExternalConversation', 'read') !== 'all') {
            $ownUserId = $this->user->getId();
        }
        return ResponseComposer::json($this->service->dashboard($ownUserId));
    }
}
