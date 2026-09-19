<?php
namespace Espo\Custom\Tools\Fusanhe;

use DateTimeImmutable;
use Espo\Core\Exceptions\BadRequest;
use Espo\Core\Exceptions\Forbidden;
use Espo\Core\Exceptions\NotFound;
use Espo\Core\Acl;
use Espo\Entities\User;
use Espo\ORM\Entity;
use Espo\ORM\EntityManager;
use stdClass;

/**
 * Hands a service conversation over to sales as a native Task. The task is
 * created through a server action (never by client-side multi-entity
 * writes), is idempotent by a unique handoff key, and validates permissions
 * on the conversation, the Task scope, and the target assignee.
 */
final class HandoffService
{
    public function __construct(
        private EntityManager $em,
        private Acl $acl,
        private User $user,
        private ServiceKernel $kernel,
    ) {}

    public function createFollowUpTask(string $conversationId, stdClass $input): array
    {
        $conversation = $this->em->getEntityById('ExternalConversation', $conversationId);
        if (!$conversation) {
            throw new NotFound('ExternalConversation not found.');
        }
        if (!$this->acl->checkEntityRead($conversation)) {
            throw new Forbidden('Not allowed to read this conversation.');
        }
        if (!$this->acl->checkScope('Task', 'create')) {
            throw new Forbidden('Not allowed to create follow-up tasks.');
        }
        $summary = trim((string) ($input->summary ?? ''));
        if ($summary === '') {
            throw new BadRequest('summary is required.');
        }
        if (mb_strlen($summary) > 2000) {
            throw new BadRequest('summary is too long.');
        }
        $assigneeId = trim((string) ($input->assignedUserId ?? ''));
        if ($assigneeId === '') {
            $assigneeId = (string) ($conversation->get('assignedUserId') ?: $this->user->getId());
        }
        $assignee = $this->em->getEntityById('User', $assigneeId);
        if (!$assignee || !$assignee->get('isActive')) {
            throw new BadRequest('Target assignee does not exist or is inactive.');
        }
        if (!$this->acl->checkAssignmentPermission($assignee)) {
            throw new Forbidden('Not allowed to assign the task to this user.');
        }
        $dateEnd = trim((string) ($input->dateEnd ?? ''));
        if ($dateEnd === '') {
            $dateEnd = (new DateTimeImmutable('+3 days'))->format('Y-m-d');
        }
        if (!preg_match('/^\d{4}-\d{2}-\d{2}$/', $dateEnd)) {
            throw new BadRequest('dateEnd must be YYYY-MM-DD.');
        }

        $key = substr(hash(
            'sha256',
            implode('|', ['handoff', $conversationId, $assigneeId, $dateEnd, trim(preg_replace('/\s+/', ' ', $summary))]),
        ), 0, 100);

        $existing = $this->repo('Task')->where(['fusanheHandoffKey' => $key])->findOne();
        if ($existing) {
            return [
                'taskId' => $existing->getId(),
                'name' => $existing->get('name'),
                'assignedUserId' => $existing->get('assignedUserId'),
                'dateEnd' => $existing->get('dateEnd'),
                'deduplicated' => true,
            ];
        }

        $customerName = (string) ($conversation->get('accountName') ?: $conversation->get('contactName') ?: $conversation->get('leadName') ?: $conversation->get('name'));
        $dueDateTime = $dateEnd . ' 18:00:00';
        $task = $this->em->getNewEntity('Task');
        $task->set([
            'name' => '跟进：' . mb_substr($customerName, 0, 60) . '（' . $dateEnd . '）',
            'parentType' => 'ExternalConversation',
            'parentId' => $conversationId,
            'status' => 'Not Started',
            'priority' => 'Normal',
            'assignedUserId' => $assigneeId,
            'dateStart' => $dueDateTime,
            'dateEnd' => $dueDateTime,
            'dateStartDate' => $dateEnd,
            'dateEndDate' => $dateEnd,
            'description' => "来自 AI 客服会话的销售跟进交接。\n\n需求摘要：" . $summary
                . "\n\n来源会话：" . $conversation->get('name')
                . "（ID " . $conversationId . "）\n渠道：" . (string) $conversation->get('channelName')
                . "\n接待人：" . (string) ($conversation->get('assignedUserName') ?: '未分配'),
            'fusanheHandoffKey' => $key,
        ]);
        if (!$this->acl->checkEntityCreate($task)) {
            throw new Forbidden('Not allowed to create this task record.');
        }
        $this->kernel->save($task);

        $this->kernel->audit(
            'handoff.created',
            'user',
            $this->user->getId(),
            'Task',
            $task->getId(),
            'success',
            [
                'conversationId' => $conversationId,
                'assignedUserId' => $assigneeId,
                'dateEnd' => $dateEnd,
                'idempotencyKey' => $key,
            ],
        );
        return [
            'taskId' => $task->getId(),
            'name' => $task->get('name'),
            'assignedUserId' => $assigneeId,
            'dateEnd' => $task->get('dateEnd'),
            'deduplicated' => false,
        ];
    }

    public function listFollowUpTasks(string $conversationId): array
    {
        $conversation = $this->em->getEntityById('ExternalConversation', $conversationId);
        if (!$conversation) {
            throw new NotFound('ExternalConversation not found.');
        }
        if (!$this->acl->checkEntityRead($conversation)) {
            throw new Forbidden('Not allowed to read this conversation.');
        }
        if (!$this->acl->checkScope('Task', 'read')) {
            throw new Forbidden('Not allowed to read tasks.');
        }
        $out = [];
        foreach ($this->repo('Task')
            ->where(['parentId' => $conversationId, 'parentType' => 'ExternalConversation'])
            ->order('createdAt', 'DESC')
            ->limit(0, 20)
            ->find() as $task) {
            if (!$this->acl->checkEntityRead($task)) {
                continue;
            }
            $out[] = [
                'id' => $task->getId(),
                'name' => $task->get('name'),
                'status' => $task->get('status'),
                'assignedUserId' => $task->get('assignedUserId'),
                'assignedUserName' => $task->get('assignedUserName'),
                'dateEnd' => $task->get('dateEnd'),
            ];
        }
        return $out;
    }

    private function repo(string $type)
    {
        return $this->em->getRDBRepository($type);
    }
}
