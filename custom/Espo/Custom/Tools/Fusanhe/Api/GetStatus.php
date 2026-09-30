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

final class GetStatus extends AbstractFusanheAction
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
            throw new Forbidden('Not allowed to read the run status.');
        }
        $status = $this->service->status();
        if ($this->user->isAdmin()) {
            return ResponseComposer::json($status);
        }

        // Conversation readers need the outbound switch, not connector account
        // metadata or agent fleet counts. Return each operational section only
        // to a role that can read the corresponding scope. Connector status is
        // reduced to health fields even for non-admin channel readers.
        $visible = [
            'outboundPaused' => $status['outboundPaused'],
            'serverTime' => $status['serverTime'],
        ];
        if ($this->acl->checkScope('ExternalChannel', 'read')) {
            $healthFields = array_fill_keys([
                'channel', 'configured', 'status', 'connected',
                'isExpired', 'lastCheckedAt',
            ], true);
            $visible['channels'] = array_map(
                static fn (array $health): array => array_intersect_key($health, $healthFields),
                $status['channels']
            );
        }
        if ($this->acl->checkScope('AutomationAgent', 'read')) {
            $visible['agents'] = $status['agents'];
        }

        return ResponseComposer::json($visible);
    }
}
