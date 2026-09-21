<?php
namespace Espo\Custom\Tools\Fusanhe\Api;

use Espo\Core\Acl;
use Espo\Core\Api\Request;
use Espo\Core\Api\Response;
use Espo\Core\Api\ResponseComposer;
use Espo\Core\Exceptions\BadRequest;
use Espo\Custom\Tools\Fusanhe\AutomationAuth;
use Espo\Custom\Tools\Fusanhe\ServiceKernel;
use Espo\Entities\User;
use Espo\ORM\EntityManager;

final class PostAgentCredentialRevoke extends AbstractFusanheAction
{
    public function __construct(
        User $user,
        Acl $acl,
        EntityManager $em,
        private AutomationAuth $auth,
        private ServiceKernel $kernel,
    ) {
        parent::__construct($user, $acl, $em);
    }

    public function process(Request $request): Response
    {
        $id = $request->getRouteParam('id');
        if (!$id) throw new BadRequest('Agent id is required.');
        $agent = $this->requireEntityScope('AutomationAgent', $id, 'edit');
        $agentKey = (string) $agent->get('agentKey');
        $this->auth->revoke($agentKey);
        $agent->set('status', 'offline');
        $this->em->saveEntity($agent, ['skipHooks' => true]);
        $this->kernel->audit('agent.credential.revoke', 'user', $this->user->getId(), 'AutomationAgent', $id);
        return ResponseComposer::json(['agentId' => $id, 'agentKey' => $agentKey, 'revoked' => true]);
    }
}
