<?php
namespace Espo\Custom\Tools\Fusanhe;

use Espo\Core\Exceptions\BadRequest;
use Espo\Core\Exceptions\Conflict;
use Espo\Core\Exceptions\Forbidden;
use Espo\Core\Exceptions\NotFound;
use Espo\Core\Acl;
use Espo\Entities\User;
use Espo\ORM\Entity;
use Espo\ORM\EntityManager;

/**
 * Conversation reception control (AI assist vs human takeover) and task
 * cancellation. All changes are server validated and audited; send-side
 * checks treat a globally paused system or a human-taken-over conversation
 * as "must not execute", consistently at claim, sending and result time.
 */
final class ControlService
{
    public function __construct(
        private EntityManager $em,
        private Acl $acl,
        private User $user,
        private ServiceKernel $kernel,
    ) {}

    public static function outboundPaused(): bool
    {
        return filter_var(getenv('FUSANHE_OUTBOUND_PAUSED') ?: 'true', FILTER_VALIDATE_BOOLEAN);
    }

    /**
     * A send may only start when outbound is globally enabled and the
     * conversation is still in AI-assist mode. Applied consistently before
     * claiming, before marking sending and before recording a success.
     */
    public function assertSendAllowed(Entity $conversation, string $stage): void
    {
        if (self::outboundPaused()) {
            throw new Conflict('Outbound is globally paused; task cannot ' . $stage . '.');
        }
        if ($conversation->get('controlMode') === 'human') {
            throw new Conflict('Conversation is under human takeover; automatic task cannot ' . $stage . '.');
        }
    }

    public function setControlMode(string $conversationId, string $mode): array
    {
        if (!in_array($mode, ['aiAssist', 'human'], true)) {
            throw new BadRequest('mode must be aiAssist or human.');
        }
        $conversation = $this->em->getEntityById('ExternalConversation', $conversationId);
        if (!$conversation) {
            throw new NotFound('ExternalConversation not found.');
        }
        if (!$this->acl->checkEntityEdit($conversation)) {
            throw new Forbidden('Not allowed to control this conversation.');
        }
        $previous = $conversation->get('controlMode');
        if ($previous === $mode) {
            return ['conversationId' => $conversationId, 'controlMode' => $mode, 'changed' => false];
        }
        $conversation->set('controlMode', $mode);
        $this->kernel->save($conversation);

        $blocked = 0;
        if ($mode === 'human') {
            $blocked = $this->repo('OutboundTask')
                ->where(['conversationId' => $conversationId, 'status' => ['pending', 'claimed']])
                ->count();
        }
        $this->kernel->audit(
            'conversation.control',
            'user',
            $this->user->getId(),
            'ExternalConversation',
            $conversationId,
            'success',
            ['from' => $previous, 'to' => $mode, 'unsentTasksBlocked' => $blocked],
        );
        return [
            'conversationId' => $conversationId,
            'controlMode' => $mode,
            'changed' => true,
            'unsentTasksBlocked' => $blocked,
        ];
    }

    public function cancelTask(string $taskId): array
    {
        $task = $this->em->getEntityById('OutboundTask', $taskId);
        if (!$task) {
            throw new NotFound('OutboundTask not found.');
        }
        if (!$this->acl->checkScope('OutboundTask', 'edit')) {
            throw new Forbidden('Not allowed to cancel outbound tasks.');
        }
        if (!$this->acl->checkEntityEdit($task)) {
            throw new Forbidden('Not allowed to cancel this outbound task.');
        }
        $status = $task->get('status');
        if (in_array($status, ['sent', 'cancelled'], true)) {
            throw new Conflict('Task already finished as ' . $status . '.');
        }
        if ($status === 'sending') {
            throw new Conflict('Task already handed to the channel; outcome unknown, cannot cancel.');
        }
        $task->set([
            'status' => 'cancelled',
            'errorMessage' => 'Cancelled by ' . ($this->user->get('name') ?: $this->user->getId()) . ' before send.',
        ]);
        $this->kernel->save($task);
        $this->kernel->audit(
            'task.cancelled',
            'user',
            $this->user->getId(),
            'OutboundTask',
            $taskId,
            'success',
            ['previousStatus' => $status],
        );
        return ['taskId' => $taskId, 'status' => 'cancelled'];
    }

    private function repo(string $type)
    {
        return $this->em->getRDBRepository($type);
    }
}
