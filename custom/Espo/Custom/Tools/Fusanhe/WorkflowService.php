<?php
namespace Espo\Custom\Tools\Fusanhe;

use DateTimeImmutable;
use DateTimeZone;
use Espo\Core\Acl;
use Espo\Core\Exceptions\BadRequest;
use Espo\Core\Exceptions\Conflict;
use Espo\Core\Exceptions\NotFound;
use Espo\ORM\Entity;
use Espo\ORM\EntityManager;
use Espo\Entities\User;
use stdClass;

/**
 * Compatibility coordination entry point for the Fusanhe inquiry workflow.
 *
 * Phase 1 responsibilities split:
 * - IdentityService: cross-channel identity mapping and manual confirmation.
 * - ControlService: reception control (human takeover) and task cancellation.
 * - HandoffService: service-to-sales handoff as native Tasks.
 * This service keeps intake, draft generation/approval and the agent task
 * pipeline, with send-side checks aligned with the pause switch and the
 * conversation control mode.
 */
final class WorkflowService
{
    public function __construct(
        private EntityManager $em,
        private AiProvider $aiProvider,
        private ServiceKernel $kernel,
        private IdentityService $identityService,
        private ControlService $controlService,
        private Acl $acl,
    ) {}

    public function intake(stdClass $input): array
    {
        $channelType = (string) ($input->channelType ?? 'Alibaba');
        $externalId = trim((string) ($input->conversationExternalId ?? ''));
        $messageId = trim((string) ($input->messageExternalId ?? ''));
        $body = trim((string) ($input->body ?? ''));
        if ($externalId === '' || $messageId === '' || $body === '') {
            throw new BadRequest('conversationExternalId, messageExternalId and body are required.');
        }
        $externalUserId = trim((string) ($input->externalUserId ?? ''));
        $email = trim((string) ($input->email ?? ''));
        $phone = trim((string) ($input->phone ?? ''));
        $senderName = trim((string) ($input->senderName ?? ''));
        $company = trim((string) ($input->company ?? ''));
        $country = (string) ($input->country ?? '');
        $accountHandle = trim((string) ($input->accountHandle ?? ''));

        if (!in_array($channelType, ['Alibaba', 'MadeInChina', 'Website', 'Email', 'WhatsApp', 'Other'], true)) {
            throw new BadRequest('Unknown channelType.');
        }
        $channel = $this->findChannel($channelType, $accountHandle);
        $conversation = $this->repo('ExternalConversation')
            ->where(['channelId' => $channel->getId(), 'externalId' => $externalId])
            ->findOne();
        if (!$conversation) {
            [$identity, $identityCreated] = $this->identityService->resolveIdentity(
                $channelType,
                $accountHandle !== '' ? $accountHandle : 'default',
                $externalUserId,
                $email,
                $phone,
                $externalId,
                [
                    'displayName' => $senderName !== '' ? $senderName : ($company !== '' ? $company : null),
                    'emailAddress' => $email ?: null,
                    'phoneNumber' => $phone ?: null,
                    'country' => $country ?: null,
                ],
            );
            $conversation = $this->kernel->create('ExternalConversation', [
                'name' => (string) ($input->subject ?? ('询盘 ' . $externalId)),
                'subject' => (string) ($input->subject ?? ''),
                'channelId' => $channel->getId(),
                'externalId' => $externalId,
                'externalUserId' => $externalUserId,
                'identityId' => $identity->getId(),
                'country' => $country,
                'language' => (string) ($input->language ?? 'en'),
                'product' => (string) ($input->product ?? ''),
                'status' => 'new',
                'controlMode' => 'aiAssist',
                // Unregistered visitors are received without a CRM customer;
                // needsManualMatch now tracks "identity not confirmed yet".
                'needsManualMatch' => $identity->get('linkStatus') !== 'confirmed',
                'unreadCount' => 0,
            ]);
        } else {
            $identity = $this->attachIdentityToConversation(
                $conversation,
                $channelType,
                $accountHandle,
                $externalUserId,
                $email,
                $phone,
                $externalId,
                $senderName,
                $company,
                $country,
            );
            $identityCreated = false;
        }

        $hash = hash('sha256', $conversation->getId() . '|inbound|' . $messageId . '|' . $body);
        $existing = $this->repo('ExternalMessage')
            ->where(['conversationId' => $conversation->getId(), 'contentHash' => $hash])
            ->findOne();
        if ($existing) {
            return [
                'deduplicated' => true,
                'conversationId' => $conversation->getId(),
                'messageId' => $existing->getId(),
                'createdLead' => false,
                'identityId' => $conversation->get('identityId'),
                'needsManualMatch' => (bool) $conversation->get('needsManualMatch'),
            ];
        }
        $sentAt = (string) ($input->sentAt ?? $this->kernel->now());
        $message = $this->kernel->create('ExternalMessage', [
            'name' => 'IN ' . $messageId,
            'conversationId' => $conversation->getId(),
            'externalId' => $messageId,
            'direction' => 'inbound',
            'senderName' => $senderName !== '' ? $senderName : 'Customer',
            'senderExternalId' => $externalUserId,
            'sentAt' => $sentAt,
            'body' => $body,
            'deliveryStatus' => 'received',
            'contentHash' => $hash,
            'rawPayload' => json_decode(json_encode($input), true),
        ]);
        $conversation->set([
            'lastMessageAt' => $sentAt,
            'lastInboundAt' => $sentAt,
            'lastMessagePreview' => mb_substr(preg_replace('/\s+/', ' ', $body), 0, 220),
            'waitingMinutes' => 0,
            'unreadCount' => ((int) $conversation->get('unreadCount')) + 1,
            'status' => 'pending',
        ]);
        $this->kernel->save($conversation);
        $this->kernel->audit('message.intake', 'connector', $channelType, 'ExternalMessage', $message->getId(), 'success', ['deduplicated' => false]);
        return [
            'deduplicated' => false,
            'conversationId' => $conversation->getId(),
            'messageId' => $message->getId(),
            // Phase 1 rule: unknown inquiries are received, never auto-converted.
            'createdLead' => false,
            'createdIdentity' => $identityCreated,
            'identityId' => $conversation->get('identityId'),
            'needsManualMatch' => (bool) $conversation->get('needsManualMatch'),
        ];
    }

    public function generateDraft(string $conversationId, ?User $user = null): array
    {
        $conversation = $this->requireEntity('ExternalConversation', $conversationId);
        if (!$this->acl->checkEntityRead($conversation)) {
            throw new NotFound('ExternalConversation not found.');
        }
        $message = $this->repo('ExternalMessage')
            ->where(['conversationId' => $conversationId, 'direction' => 'inbound'])
            ->order('sentAt', 'DESC')
            ->findOne();
        if (!$message) {
            throw new Conflict('No inbound message available.');
        }
        $knowledge = $this->collectKnowledge();
        // Approved and still-valid certificates may back factual claims; every
        // item carries a source id so citations survive into the draft.
        if (Features::enabled('certificates')) {
            $certs = $this->repo('FusanheCertificate')->where([
                'status' => 'approved',
                'OR' => [['validTo' => null], ['validTo>=' => date('Y-m-d')]],
            ])->limit(3)->find();
            foreach ($certs as $cert) {
                $scope = (string) $cert->get('scopeLevel');
                $subject = $cert->get('productName') ?: ($cert->get('factoryName') ?: $cert->get('batchCode') ?: '');
                $text = sprintf(
                    '[%s] Issued by %s, No. %s, valid %s..%s, scope: %s (%s). Markets: %s',
                    (string) $cert->get('type'),
                    (string) ($cert->get('issuer') ?: 'n/a'),
                    (string) ($cert->get('certificateNo') ?: 'n/a'),
                    (string) ($cert->get('validFrom') ?: '?'),
                    (string) ($cert->get('validTo') ?: 'open'),
                    $scope,
                    (string) $subject,
                    (string) ($cert->get('markets') ?: 'n/a')
                );
                $knowledge[] = ['id' => 'cert:' . $cert->getId(), 'title' => (string) $cert->get('name'), 'text' => $text];
            }
        }
        $history = [];
        foreach ($this->repo('ExternalMessage')->where(['conversationId' => $conversationId])->order('sentAt', 'ASC')->limit(20)->find() as $item) {
            $history[] = ['direction' => $item->get('direction'), 'body' => $item->get('body'), 'sentAt' => $item->get('sentAt')];
        }
        $identity = $conversation->get('identityId')
            ? $this->em->getEntityById('ExternalIdentity', (string) $conversation->get('identityId'))
            : null;
        $customerContext = [
            'displayName' => $identity?->get('displayName') ?: (string) ($conversation->get('externalUserId') ?: ''),
            'country' => $conversation->get('country'),
            'language' => $conversation->get('language'),
            'emailAddress' => $identity?->get('emailAddress'),
            'phoneNumber' => $identity?->get('phoneNumber'),
            'linkedCustomer' => $conversation->get('accountName') ?: $conversation->get('contactName') ?: $conversation->get('leadName'),
            // Reception owner (接待人) and confirmed business context for the AI.
            'ownerName' => $conversation->get('assignedUserName'),
            'identityConfirmed' => $identity ? $identity->get('linkStatus') === 'confirmed' : false,
        ];
        $result = $this->aiProvider->generate([
            'country' => $conversation->get('country'),
            'language' => $conversation->get('language'),
            'product' => $conversation->get('product'),
            'message' => $message->get('body'),
            'history' => $history,
            'opportunityStage' => null,
            'customer' => $customerContext,
            'companyRules' => ['Do not promise price, MOQ, lead time, certification, payment, discounts, quality or compensation without approved evidence.'],
            'knowledge' => $knowledge,
        ]);
        $draft = $this->kernel->create('AIReplyDraft', [
            'name' => 'AI 草稿 ' . gmdate('Y-m-d H:i'),
            'conversationId' => $conversationId,
            'sourceMessageId' => $message->getId(),
            'draftText' => $result['draftText'],
            'intent' => $result['intent'],
            'summaryZh' => $result['summaryZh'],
            'suggestedLanguage' => $result['suggestedLanguage'],
            'riskLevel' => $result['riskLevel'],
            'confidence' => $result['confidence'],
            'missingInformation' => $result['missingInformation'],
            'citedKnowledge' => $result['citedKnowledge'],
            'modelProvider' => $result['provider'],
            'modelName' => $result['model'],
            'promptVersion' => 'phase1-v1',
            'status' => 'generated',
        ]);
        if ($conversation->get('status') !== 'closed') {
            $conversation->set('status', 'waitingApproval');
            $this->kernel->save($conversation);
        }
        $this->kernel->audit('draft.generated', 'user', $user?->getId() ?? 'system', 'AIReplyDraft', $draft->getId(), 'success', [
            'provider' => $result['provider'],
            'conversationId' => $conversationId,
            'knowledgeUsed' => array_map(fn($k) => $k['id'], $knowledge),
        ]);
        return ['draftId' => $draft->getId()] + $result;
    }

    public function createManualDraft(string $conversationId, User $user, stdClass $input): array
    {
        $conversation = $this->requireEntity('ExternalConversation', $conversationId);
        if (!$this->acl->checkEntityRead($conversation)) {
            throw new NotFound('ExternalConversation not found.');
        }
        if (!$this->acl->checkScope('AIReplyDraft', 'create')) {
            throw new Conflict('Not allowed to create drafts.');
        }
        $draftText = trim((string) ($input->draftText ?? ''));
        if ($draftText === '') {
            throw new BadRequest('draftText is required.');
        }
        $message = $this->repo('ExternalMessage')
            ->where(['conversationId' => $conversationId, 'direction' => 'inbound'])
            ->order('sentAt', 'DESC')
            ->findOne();
        if (!$message) {
            throw new Conflict('No inbound message to reply to.');
        }
        $draft = $this->kernel->create('AIReplyDraft', [
            'name' => '人工草稿 ' . gmdate('Y-m-d H:i'),
            'conversationId' => $conversationId,
            'sourceMessageId' => $message->getId(),
            'draftText' => $draftText,
            'intent' => '人工回复',
            'summaryZh' => '客服手动撰写的回复草稿。',
            'suggestedLanguage' => (string) ($conversation->get('language') ?: 'en'),
            'riskLevel' => 'low',
            'confidence' => 1.0,
            'missingInformation' => [],
            'citedKnowledge' => [],
            'modelProvider' => 'manual',
            'modelName' => 'human',
            'promptVersion' => 'phase1-manual',
            'status' => 'generated',
        ]);
        if ($conversation->get('status') !== 'closed') {
            $conversation->set('status', 'waitingApproval');
            $this->kernel->save($conversation);
        }
        $this->kernel->audit('draft.manual', 'user', $user->getId(), 'AIReplyDraft', $draft->getId(), 'success', ['conversationId' => $conversationId]);
        return [
            'draftId' => $draft->getId(),
            'provider' => 'manual',
            'draftText' => $draftText,
        ];
    }

    public function approve(string $draftId, User $user, ?string $editedText): array
    {
        $draft = $this->requireEntity('AIReplyDraft', $draftId);
        // Entity-level gate: a user with OutboundTask:create but no access to
        // the conversation must neither read the reply nor approve it.
        if (!$this->acl->checkEntityRead($draft)) {
            throw new NotFound('AIReplyDraft not found.');
        }
        $conversation = $this->requireEntity('ExternalConversation', (string) $draft->get('conversationId'));
        if (!$this->acl->checkEntityRead($conversation)) {
            throw new NotFound('ExternalConversation not found.');
        }
        if (!in_array($draft->get('status'), ['generated', 'edited'], true)) {
            throw new Conflict('Draft is not approvable.');
        }
        if (
            $editedText !== null && trim($editedText) !== '' &&
            trim($editedText) !== trim((string) $draft->get('draftText'))
        ) {
            $draft->set(['draftText' => trim($editedText), 'status' => 'edited', 'wasEdited' => true]);
        }
        $key = hash('sha256', $draft->getId() . '|' . $draft->get('draftText'));
        $task = $this->repo('OutboundTask')->where(['idempotencyKey' => $key])->findOne();
        $deduplicated = (bool) $task;
        // Immutable snapshot: the approved text is frozen into the task; later
        // draft edits cannot change what will be sent.
        $snapshot = (string) $draft->get('draftText');
        $executionMode = $this->resolveExecutionMode($conversation);
        if (!$task) {
            $task = $this->kernel->create('OutboundTask', [
                'name' => '发送任务 ' . substr($key, 0, 10),
                'conversationId' => $conversation->getId(),
                'replyDraftId' => $draft->getId(),
                'channelId' => $conversation->get('channelId'),
                'status' => 'pending',
                'idempotencyKey' => $key,
                'executionMode' => $executionMode,
                'contentSnapshot' => $snapshot,
                'payload' => [
                    'body' => $snapshot,
                    'draftId' => $draft->getId(),
                    'snapshotAt' => $this->kernel->now(),
                    'executionMode' => $executionMode,
                ],
            ]);
        }
        $draft->set(['status' => 'approved', 'approvedById' => $user->getId(), 'approvedAt' => $this->kernel->now()]);
        $this->kernel->save($draft);
        if ($conversation->get('status') !== 'closed') {
            $conversation->set('status', 'readyToSend');
            $this->kernel->save($conversation);
        }
        $this->kernel->audit('draft.approved', 'user', $user->getId(), 'OutboundTask', $task->getId(), 'success', [
            'idempotencyKey' => $key,
            'executionMode' => $executionMode,
            'deduplicated' => $deduplicated,
        ]);
        return [
            'taskId' => $task->getId(),
            'idempotencyKey' => $key,
            'deduplicated' => $deduplicated,
            'executionMode' => $executionMode,
        ];
    }

    public function registerAgent(stdClass $input): array
    {
        $key = trim((string) ($input->agentKey ?? ''));
        if ($key === '') {
            throw new BadRequest('agentKey is required.');
        }
        $tx = $this->em->getTransactionManager();
        $creating = false;
        $tx->start();
        try {
            // A row lock serializes credential rotation. Two successful
            // rotations therefore leave only the final credential usable.
            $agent = $this->repo('AutomationAgent')
                ->forUpdate()
                ->where(['agentKey' => $key])
                ->findOne();
            $creating = !$agent;
            $credentialIssued = $creating
                || trim((string) ($agent->get('credentialHash') ?? '')) === ''
                || (($input->rotateCredential ?? false) === true);
            $values = [
                'status' => 'online',
                'lastHeartbeatAt' => $this->kernel->now(),
                'capabilities' => (array) ($input->capabilities ?? []),
                'lastError' => null,
            ];
            if (property_exists($input, 'clientVersion')) {
                $values['clientVersion'] = mb_substr(trim((string) $input->clientVersion), 0, 100);
            }
            $agentToken = null;
            if ($credentialIssued) {
                $agentToken = rtrim(strtr(base64_encode(random_bytes(32)), '+/', '-_'), '=');
                $credentialHash = password_hash($agentToken, PASSWORD_ARGON2ID);
                if ($credentialHash === false) {
                    throw new \RuntimeException('Unable to issue agent credential.');
                }
                $values['credentialHash'] = $credentialHash;
                $values['credentialStatus'] = 'active';
            }
            if ($creating) {
                $agent = $this->em->getNewEntity('AutomationAgent');
                $agent->set([
                    'name' => (string) ($input->name ?? $key),
                    'agentKey' => $key,
                    'mode' => 'mock',
                ]);
            }
            $mode = (string) ($input->mode ?? '');
            if (in_array($mode, ['mock', 'real'], true)) {
                $values['mode'] = $mode;
            }
            $agent->set($values);
            $this->kernel->save($agent);
            $this->kernel->audit('agent.register', 'agent', $key, 'AutomationAgent', $agent->getId());
            $tx->commit();

            $response = [
                'agentId' => $agent->getId(),
                'status' => 'online',
                'mode' => $agent->get('mode'),
                'credentialIssued' => $credentialIssued,
            ];
            if ($credentialIssued) {
                $response['agentToken'] = $agentToken;
            }
            return $response;
        } catch (\Throwable $e) {
            $tx->rollback();
            // The unique agentKey index may race before a row exists to lock.
            // Do not expose a database exception; callers can retry safely.
            if ($creating && $this->repo('AutomationAgent')->where(['agentKey' => $key])->findOne()) {
                throw new Conflict('Agent registration conflicted; retry.');
            }
            throw $e;
        }
    }

    public function heartbeat(stdClass $input): array
    {
        $key = (string) ($input->agentKey ?? '');
        $agent = $this->repo('AutomationAgent')->where(['agentKey' => $key])->findOne();
        if (!$agent) {
            throw new NotFound('Agent not registered.');
        }
        $status = (string) ($input->status ?? 'online');
        $agent->set(['status' => $status, 'lastHeartbeatAt' => $this->kernel->now(), 'lastError' => $input->lastError ?? null]);
        $this->kernel->save($agent);
        $this->kernel->audit('agent.heartbeat', 'agent', $key, 'AutomationAgent', $agent->getId(), $status === 'online' ? 'success' : 'failure', ['status' => $status]);
        return ['ok' => true];
    }

    public function claim(stdClass $input): array
    {
        $key = trim((string) ($input->agentKey ?? ''));
        if ($key === '') {
            throw new BadRequest('agentKey is required.');
        }
        $agent = $this->repo('AutomationAgent')->where(['agentKey' => $key])->findOne();
        if (!$agent) {
            throw new NotFound('Agent not registered.');
        }
        if ($agent->get('status') !== 'online') {
            throw new Conflict('Agent is not online.');
        }
        if (ControlService::outboundPaused()) {
            return ['task' => null, 'paused' => true];
        }
        // Mock agents can only execute mock tasks; real agents only real ones.
        $mode = (string) ($agent->get('mode') ?: 'mock');
        $capabilities = (array) ($agent->get('capabilities') ?? []);

        $tx = $this->em->getTransactionManager();
        $tx->start();
        try {
            $now = $this->kernel->now();
            foreach ($this->repo('OutboundTask')->where(['status' => 'claimed', 'claimExpiresAt<' => $now])->find() as $expired) {
                $expired->set(['status' => 'pending', 'claimedBy' => null, 'claimedAt' => null, 'claimExpiresAt' => null]);
                $this->kernel->save($expired);
            }

            $pendingTasks = $this->em->getRDBRepository('OutboundTask')
                ->forUpdate()
                ->where(['status' => 'pending', 'executionMode' => $mode])
                ->order('createdAt', 'ASC')
                ->find();
            $task = null;
            foreach ($pendingTasks as $candidate) {
                if (!empty($capabilities)) {
                    $channel = $this->em->getEntityById('ExternalChannel', (string) $candidate->get('channelId'));
                    $channelType = $channel ? (string) $channel->get('type') : '';
                    if ($channelType !== '' && !in_array($channelType, $capabilities, true)) {
                        continue;
                    }
                }
                $conversation = $this->em->getEntityById('ExternalConversation', (string) $candidate->get('conversationId'));
                // Human takeover blocks automatic task execution.
                if ($conversation && $conversation->get('controlMode') === 'human') {
                    continue;
                }
                $active = $this->repo('OutboundTask')->where([
                    'conversationId' => $candidate->get('conversationId'),
                    'status' => ['claimed', 'sending'],
                ])->findOne();
                if ($active && $active->getId() !== $candidate->getId()) {
                    continue;
                }
                $task = $candidate;
                break;
            }

            if (!$task) {
                $tx->commit();
                return ['task' => null, 'paused' => false];
            }

            $task->set([
                'status' => 'claimed',
                'claimedBy' => $key,
                'claimedAt' => $now,
                'claimExpiresAt' => (new DateTimeImmutable('+5 minutes'))->setTimezone(new DateTimeZone('UTC'))->format('Y-m-d H:i:s'),
            ]);
            $this->kernel->save($task);
            $tx->commit();

            $this->kernel->audit('task.claimed', 'agent', $key, 'OutboundTask', $task->getId());
            return ['paused' => false, 'task' => $this->taskPayload($task)];
        } catch (\Throwable $e) {
            $tx->rollback();
            throw $e;
        }
    }

    public function markSending(string $id, stdClass $input): array
    {
        $task = $this->ownedTask($id, (string) ($input->agentKey ?? ''));
        if ($task->get('status') !== 'claimed') {
            throw new Conflict('Task must be claimed first.');
        }
        $conversation = $this->requireEntity('ExternalConversation', (string) $task->get('conversationId'));
        $this->controlService->assertSendAllowed($conversation, 'start sending');
        $task->set('status', 'sending');
        $this->kernel->save($task);
        // The task status is the single source of truth for the send state;
        // the conversation is no longer flipped to 'sending'.
        $this->kernel->audit('task.sending', 'agent', (string) $task->get('claimedBy'), 'OutboundTask', $id);
        return ['ok' => true];
    }

    public function reportResult(string $id, stdClass $input): array
    {
        $task = $this->ownedTask($id, (string) ($input->agentKey ?? ''));
        if ($task->get('status') === 'sent') {
            return ['ok' => true, 'status' => 'sent', 'idempotent' => true];
        }
        if (!in_array($task->get('status'), ['claimed', 'sending'], true)) {
            throw new Conflict('Task is not active.');
        }

        $success = (bool) ($input->success ?? false);
        if ($success) {
            $platformMessageId = trim((string) ($input->platformMessageId ?? ''));
            if ($platformMessageId === '') {
                throw new BadRequest('platformMessageId is required for successful result.');
            }
            $conversation = $this->requireEntity('ExternalConversation', (string) $task->get('conversationId'));
            // Recording the outcome of a task already handed to the channel is
            // bookkeeping, not a new send: pause/takeover gates live at claim
            // and markSending time. Blocking here would wedge the task in
            // 'sending' forever (undeliverable receipts, blocked pipeline).
            $executionMode = (string) ($task->get('executionMode') ?: 'mock');

            $task->set([
                'status' => 'sent',
                'platformMessageId' => $platformMessageId,
                'completedAt' => $this->kernel->now(),
                'errorMessage' => null,
            ]);
            $draft = $this->requireEntity('AIReplyDraft', (string) $task->get('replyDraftId'));
            $draft->set('status', 'sent');
            $this->kernel->save($draft);

            // Mock receipts are explicitly marked as simulated - they must
            // never look like a real customer received a message.
            $deliveryStatus = $executionMode === 'real' ? 'sent' : 'mockSent';
            $body = $this->taskBody($task, $draft);
            $hash = hash('sha256', $conversation->getId() . '|outbound|' . $task->get('idempotencyKey'));
            if (!$this->repo('ExternalMessage')->where(['conversationId' => $conversation->getId(), 'contentHash' => $hash])->findOne()) {
                $this->kernel->create('ExternalMessage', [
                    'name' => 'OUT ' . substr($hash, 0, 8),
                    'conversationId' => $conversation->getId(),
                    'externalId' => $platformMessageId,
                    'direction' => 'outbound',
                    'senderName' => '福三和',
                    'sentAt' => $this->kernel->now(),
                    'body' => $body,
                    'deliveryStatus' => $deliveryStatus,
                    'contentHash' => $hash,
                ]);
            }
            $now = $this->kernel->now();
            if ($conversation->get('status') !== 'closed') {
                $conversation->set([
                    // Send results stay on the task; the conversation only
                    // records that a reply happened. Closed stays terminal.
                    'status' => 'replied',
                    'lastOutboundAt' => $now,
                    'lastMessageAt' => $now,
                    'lastMessagePreview' => mb_substr(preg_replace('/\s+/', ' ', $body), 0, 220),
                    'waitingMinutes' => null,
                    'unreadCount' => 0,
                ]);
                if ($conversation->get('lastInboundAt')) {
                    $conversation->set('firstResponseMinutes', max(0, (int) round((time() - strtotime((string) $conversation->get('lastInboundAt'))) / 60)));
                }
                $this->kernel->save($conversation);
            }
        } else {
            $retries = ((int) $task->get('retryCount')) + 1;
            $task->set([
                'retryCount' => $retries,
                'status' => $retries < 3 ? 'pending' : 'failed',
                'errorMessage' => (string) ($input->errorMessage ?? 'Unknown send error'),
                'claimedBy' => null,
                'claimExpiresAt' => null,
            ]);
        }

        $this->kernel->save($task);
        $this->kernel->audit('task.result', 'agent', (string) ($input->agentKey ?? ''), 'OutboundTask', $id, $success ? 'success' : 'failure', ['platformMessageId' => $input->platformMessageId ?? null]);
        return ['ok' => true, 'status' => $task->get('status')];
    }

    public function dashboard(?string $ownUserId = null): array
    {
        $today = gmdate('Y-m-d 00:00:00');
        $count = fn(string $type, array $where = []) => $this->repo($type)->where($where)->count();
        $conversations = $this->repo('ExternalConversation')->where($ownWhere ? ['createdAt>=' => $today, ...$ownWhere] : ['createdAt>=' => $today])->find();
        $channels = [];
        $byAssignedUser = [];
        foreach ($conversations as $c) {
            $channel = $this->em->getEntityById('ExternalChannel', (string) $c->get('channelId'));
            $k = $channel ? (string) $channel->get('type') : 'Unknown';
            $channels[$k] = ($channels[$k] ?? 0) + 1;
            $owner = (string) ($c->get('assignedUserName') ?: '未分配');
            $byAssignedUser[$owner] = ($byAssignedUser[$owner] ?? 0) + 1;
        }

        $open = $this->repo('ExternalConversation')->where($ownWhere ? ['status' => ['new', 'pending', 'drafted', 'waitingApproval'], ...$ownWhere] : ['status' => ['new', 'pending', 'drafted', 'waitingApproval']])->find();
        $slaBreached = 0;
        foreach ($open as $c) {
            $waiting = $c->get('lastInboundAt') ? max(0, (int) floor((time() - strtotime((string) $c->get('lastInboundAt'))) / 60)) : null;
            if ($waiting !== null && $waiting >= 120) {
                $slaBreached++;
            }
        }

        $responded = $this->repo('ExternalConversation')->where($ownWhere ? ['firstResponseMinutes!=' => null, ...$ownWhere] : ['firstResponseMinutes!=' => null])->find();
        $sum = 0;
        $n = 0;
        foreach ($responded as $c) {
            $sum += (int) $c->get('firstResponseMinutes');
            $n++;
        }
        $draftTotal = $count('AIReplyDraft');
        $edited = $count('AIReplyDraft', ['wasEdited' => true]);
        $taskTotal = $count('OutboundTask');
        $sent = $count('OutboundTask', ['status' => 'sent']);

        return [
            'todayInquiries' => count($conversations),
            'byChannel' => $channels,
            'byAssignedUser' => $byAssignedUser,
            'unassigned' => $ownUserId ? 0 : $count('ExternalConversation', ['assignedUserId' => null]),
            'waitingReply' => $ownUserId ? $count('ExternalConversation', ['status' => ['new', 'pending'], ...$ownWhere]) : $count('ExternalConversation', ['status' => ['new', 'pending']]),
            'waitingApproval' => $ownUserId ? $count('ExternalConversation', ['status' => 'waitingApproval', ...$ownWhere]) : $count('ExternalConversation', ['status' => 'waitingApproval']),
            'slaBreached' => $slaBreached,
            'averageFirstResponseMinutes' => $n ? round($sum / $n, 1) : null,
            'aiDrafts' => $draftTotal,
            'humanEditRate' => $draftTotal ? round($edited / $draftTotal, 3) : 0,
            'sendSuccessRate' => $taskTotal ? round($sent / $taskTotal, 3) : 0,
            'failedTasks' => $count('OutboundTask', ['status' => 'failed']),
            'identitiesAwaitingConfirmation' => $count('ExternalIdentity', ['linkStatus' => 'unlinked']),
            'humanTakeoverConversations' => $count('ExternalConversation', ['controlMode' => 'human']),
        ];
    }

    public function status(): array
    {
        $channels = [];
        foreach (['Alibaba', 'MadeInChina', 'Website', 'Email'] as $type) {
            $connector = $this->getConnector($type);
            $channels[$type] = $connector->healthCheck();
        }
        return [
            'outboundPaused' => ControlService::outboundPaused(),
            'channels' => $channels,
            'agents' => [
                'total' => $this->repo('AutomationAgent')->count(),
                'online' => $this->repo('AutomationAgent')->where(['status' => 'online'])->count(),
                'offline' => $this->repo('AutomationAgent')->where(['status' => 'offline'])->count(),
            ],
            'serverTime' => $this->kernel->now(),
        ];
    }

    public function getConnector(string $channelType): Connector\Connector
    {
        return match ($channelType) {
            'Alibaba' => new Connector\AlibabaConnector(),
            'MadeInChina' => new Connector\MadeInChinaConnector(),
            'Website' => new Connector\WebsiteConnector(),
            'Email' => new Connector\EmailConnector(),
            default => new Connector\MockConnector(),
        };
    }

    /**
     * Approved knowledge in its validity window that the requesting user can
     * read. Checksum changes send documents back to draft (see scanner), so
     * stale approvals cannot enter the AI context.
     */
    private function collectKnowledge(): array
    {
        $today = gmdate('Y-m-d');
        $docs = $this->repo('KnowledgeDocument')->where(['approvalStatus' => 'approved'])->limit(0, 50)->find();
        $knowledge = [];
        foreach ($docs as $doc) {
            $from = $doc->get('effectiveFrom');
            $to = $doc->get('effectiveTo');
            if ($from && (string) $from > $today) {
                continue;
            }
            if ($to && (string) $to < $today) {
                continue;
            }
            if (!$this->acl->checkEntityRead($doc)) {
                continue;
            }
            $knowledge[] = ['id' => $doc->getId(), 'title' => $doc->get('name'), 'text' => mb_substr((string) $doc->get('extractedText'), 0, 3000)];
            if (count($knowledge) >= 5) {
                break;
            }
        }
        return $knowledge;
    }

    private function findChannel(string $channelType, string $accountHandle): Entity
    {
        $handleKey = $accountHandle !== '' ? $accountHandle : 'default';
        foreach ($this->repo('ExternalChannel')->where(['type' => $channelType])->find() as $candidate) {
            $candidateHandle = (string) ($candidate->get('accountHandle') ?: 'default');
            if ($candidateHandle === $handleKey) {
                // A disabled channel must not accept inquiries.
                if (!$candidate->get('enabled')) {
                    throw new Conflict('Channel is disabled; inquiry intake rejected.');
                }
                return $candidate;
            }
        }
        return $this->kernel->create('ExternalChannel', [
            'name' => $handleKey === 'default' ? $channelType . '（模拟）' : $channelType . ' · ' . $accountHandle,
            'type' => $channelType,
            'accountHandle' => $handleKey,
            'enabled' => true,
            'connectionStatus' => 'healthy',
        ]);
    }

    private function attachIdentityToConversation(
        Entity $conversation,
        string $channelType,
        string $accountHandle,
        string $externalUserId,
        string $email,
        string $phone,
        string $externalId,
        string $senderName,
        string $company,
        string $country,
    ): Entity {
        $identityId = (string) ($conversation->get('identityId') ?? '');
        $identity = null;
        if ($identityId !== '') {
            $identity = $this->em->getEntityById('ExternalIdentity', $identityId);
        }
        if (!$identity) {
            [$identity,] = $this->identityService->resolveIdentity(
                $channelType,
                $accountHandle !== '' ? $accountHandle : 'default',
                $externalUserId,
                $email,
                $phone,
                $externalId,
                [
                    'displayName' => $senderName !== '' ? $senderName : ($company !== '' ? $company : null),
                    'emailAddress' => $email ?: null,
                    'phoneNumber' => $phone ?: null,
                    'country' => $country ?: null,
                ],
            );
            $conversation->set('identityId', $identity->getId());
        }
        if ($identity->get('linkStatus') !== 'confirmed') {
            $conversation->set('needsManualMatch', true);
        }
        return $identity;
    }

    private function resolveExecutionMode(Entity $conversation): string
    {
        $channel = $this->em->getEntityById('ExternalChannel', (string) $conversation->get('channelId'));
        $config = $channel ? $channel->get('config') : null;
        if (is_array($config) && !empty($config['realOutbound'])) {
            return 'real';
        }
        // No channel in this project has a real send path yet: everything is
        // mock until a connector flips realOutbound on its channel record.
        return 'mock';
    }

    /**
     * The immutable approved snapshot wins; the fallback to the live draft
     * only covers tasks created before snapshots existed.
     */
    private function taskBody(Entity $task, Entity $draft): string
    {
        $snapshot = $task->get('contentSnapshot');
        if (is_string($snapshot) && trim($snapshot) !== '') {
            return $snapshot;
        }
        $payload = $task->get('payload');
        if (is_array($payload) && isset($payload['body']) && is_string($payload['body']) && $payload['body'] !== '') {
            return $payload['body'];
        }
        return (string) $draft->get('draftText');
    }

    private function taskPayload(Entity $task): array
    {
        $draft = $this->requireEntity('AIReplyDraft', (string) $task->get('replyDraftId'));
        $body = $this->taskBody($task, $draft);
        $convId = (string) $task->get('conversationId');
        $conversation = $convId !== '' ? $this->em->getEntityById('ExternalConversation', $convId) : null;
        $channelId = (string) $task->get('channelId');
        $channel = $channelId !== '' ? $this->em->getEntityById('ExternalChannel', $channelId) : null;

        return [
            'id' => $task->getId(),
            'idempotencyKey' => $task->get('idempotencyKey'),
            'conversationId' => $convId,
            'inquiryId' => $conversation ? (string) ($conversation->get('externalId') ?: '') : '',
            'buyerName' => $conversation ? (string) ($conversation->get('buyerName') ?: $conversation->get('name') ?: '') : '',
            'channelId' => $channelId,
            'channelType' => $channel ? (string) ($channel->get('type') ?: 'Alibaba') : 'Alibaba',
            'executionMode' => $task->get('executionMode') ?: 'mock',
            'body' => $body,
            'triggerType' => (string) ($draft->get('triggerType') ?: 'manual'),
            'claimExpiresAt' => $task->get('claimExpiresAt'),
        ];
    }

    private function ownedTask(string $id, string $key): Entity
    {
        $task = $this->requireEntity('OutboundTask', $id);
        if ($key === '' || $task->get('claimedBy') !== $key) {
            throw new Conflict('Task is not claimed by this agent.');
        }
        return $task;
    }

    private function requireEntity(string $type, string $id): Entity
    {
        $e = $this->em->getEntityById($type, $id);
        if (!$e) {
            throw new NotFound("$type not found.");
        }
        return $e;
    }

    private function repo(string $type)
    {
        return $this->em->getRDBRepository($type);
    }
}
