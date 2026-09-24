<?php
namespace Espo\Custom\Tools\Fusanhe;

use DateTimeImmutable;
use DateTimeZone;
use Espo\Core\Exceptions\BadRequest;
use Espo\Core\Exceptions\Conflict;
use Espo\Core\Exceptions\Forbidden;
use Espo\ORM\Entity;
use Espo\ORM\EntityManager;
use stdClass;

/**
 * Inbound-only Alibaba history importer.  It persists a bounded batch as one
 * transaction and intentionally has no reply-generation or delivery side
 * effects; the normal workflow owns those later steps.
 */
final class AlibabaSyncService
{
    public const MAX_MESSAGES = 100;
    public const MAX_BODY = 200000;
    public const MAX_BATCH = 2000000;

    public function __construct(
        private EntityManager $em,
        private ServiceKernel $kernel,
        private IdentityService $identityService,
    ) {}

    public function sync(stdClass $input, Entity $agent): array
    {
        $this->validate($input, $agent);
        $requestId = trim((string) $input->requestId);
        $jobId = trim((string) $input->jobId);
        $accountHandle = trim((string) $input->accountHandle);
        // Hash the canonical request before starting the transaction.  The
        // audit record keeps only this digest, never the body-bearing input.
        $payloadHash = $this->canonicalPayloadHash($input);
        $tx = $this->em->getTransactionManager();
        $tx->start();
        try {
            $prior = $this->repo('AutomationAudit')->where(['requestId' => $requestId])->findOne();
            $priorResponse = $this->replayResponse($prior, $jobId, $payloadHash);
            if ($priorResponse !== null) {
                $tx->commit();
                return $priorResponse;
            }

            $mode = (string) $input->syncMode;
            $conversationInput = $input->conversation;
            $channel = $this->findChannel($accountHandle);
            $inquiryId = trim((string) $conversationInput->inquiryId);
            $conversation = $this->repo('ExternalConversation')
                ->where(['channelId' => $channel->getId(), 'externalId' => $inquiryId])
                ->findOne();
            $createdConversation = !$conversation;
            if (!$conversation) {
                $conversation = $this->em->getNewEntity('ExternalConversation');
                $conversation->set([
                    'name' => mb_substr((trim((string) ($conversationInput->buyerName ?? '')) ?: 'Alibaba 询盘') . ' · ' . $inquiryId, 0, 255),
                    'channelId' => $channel->getId(),
                    'externalId' => $inquiryId,
                    'externalUserId' => trim((string) ($conversationInput->buyerExternalId ?? '')),
                    'subject' => (string) ($conversationInput->subject ?? ''),
                    'country' => (string) ($conversationInput->country ?? ''),
                    'status' => 'new',
                    'unreadCount' => 0,
                    'needsManualMatch' => false,
                ]);
                $this->kernel->save($conversation);
            }

            $buyerExternalId = trim((string) ($conversationInput->buyerExternalId ?? ''));
            $buyerEmail = trim((string) ($conversationInput->buyerEmail ?? ''));
            $buyerPhone = trim((string) ($conversationInput->buyerPhone ?? ''));
            // Without a platform-stable buyer id, this must remain anonymous
            // per inquiry.  Contact data remains profile-only and is assessed
            // later by the explicit strong-evidence customer matcher.
            $identityEmail = $buyerExternalId === '' ? '' : $buyerEmail;
            $identityPhone = $buyerExternalId === '' ? '' : $buyerPhone;
            $profile = [
                'displayName' => trim((string) ($conversationInput->buyerName ?? '')),
                'emailAddress' => $buyerEmail,
                'phoneNumber' => $buyerPhone,
                'country' => trim((string) ($conversationInput->country ?? '')),
            ];
            $identity = $this->existingConversationIdentity($conversation);
            if ($identity === null) {
                [$identity,] = $this->identityService->resolveIdentity(
                    'Alibaba',
                    $accountHandle,
                    $buyerExternalId,
                    $identityEmail,
                    $identityPhone,
                    $inquiryId,
                    $profile,
                );
            } else {
                $this->identityService->refreshIntegrationProfile($identity, $buyerExternalId, $profile);
            }
            $customer = $this->identityService->resolveAutomaticCustomer($identity, $inquiryId);
            $this->attachCustomer($conversation, $identity, $customer);
            $this->kernel->save($conversation);

            $createdMessages = 0;
            $deduplicatedMessages = 0;
            $prevSentAt = null;
            foreach ($input->messages as $messageInput) {
                $externalId = trim((string) $messageInput->externalId);
                $body = trim((string) $messageInput->body);
                $direction = (string) $messageInput->direction;
                $hash = hash('sha256', $conversation->getId() . '|' . $direction . '|' . $externalId . '|' . $body);
                $existing = $this->repo('ExternalMessage')
                    ->where(['conversationId' => $conversation->getId(), 'externalId' => $externalId])
                    ->findOne();
                if (!$existing) {
                    $existing = $this->repo('ExternalMessage')
                        ->where(['conversationId' => $conversation->getId(), 'contentHash' => $hash])
                        ->findOne();
                }
                if ($existing) {
                    $deduplicatedMessages++;
                    $prevSentAt = (string) $existing->get('sentAt');
                    continue;
                }

                $confidence = (string) $messageInput->timestampConfidence;
                $sourceTimestampRaw = isset($messageInput->sourceTimestampRaw) ? (string) $messageInput->sourceTimestampRaw : '';
                $sentAtRaw = isset($messageInput->sentAt) ? (string) $messageInput->sentAt : '';
                $sentAt = $confidence === 'low'
                    ? $this->lowConfidenceTime($conversationInput, $sentAtRaw, $prevSentAt, (int) $messageInput->sourceSequence)
                    : $this->normaliseTime($sentAtRaw);
                $prevSentAt = $sentAt;
                $message = $this->em->getNewEntity('ExternalMessage');
                $message->set([
                    'name' => ($direction === 'inbound' ? 'IN ' : 'OUT ') . $externalId,
                    'conversationId' => $conversation->getId(),
                    'externalId' => $externalId,
                    'direction' => $direction,
                    'senderName' => (string) ($messageInput->senderName ?? '') ?: ($direction === 'inbound' ? (string) ($conversationInput->buyerName ?? '买家') : '我方客服'),
                    'senderExternalId' => (string) ($messageInput->senderExternalId ?? ''),
                    'sentAt' => $sentAt,
                    'body' => $body,
                    'deliveryStatus' => $direction === 'outbound' ? 'sent' : 'received',
                    'contentHash' => $hash,
                    'sourceTimestampRaw' => $sourceTimestampRaw,
                    'timestampConfidence' => $confidence,
                    'sourceSequence' => $messageInput->sourceSequence,
                    'messageType' => (string) $messageInput->messageType,
                    // Never store a connector request wholesale: it can include
                    // credentials and buyers' data unrelated to this message.
                    'rawPayload' => ['source' => 'Alibaba', 'externalId' => $externalId],
                ]);
                $this->kernel->save($message);
                $createdMessages++;
            }

            $finalized = $mode === 'incremental' || (bool) ($input->finalBatch ?? false);
            if ($finalized) {
                $this->refreshConversationState($conversation, $conversationInput);
                if ($mode === 'backfill') {
                    $conversation->set('backfillCompletedAt', $this->kernel->now());
                }
                $this->kernel->save($conversation);
            }

            $response = [
                'requestId' => $requestId,
                'conversationId' => $conversation->getId(),
                'identityId' => $identity->getId(),
                'leadId' => $customer['targetType'] === 'Lead' ? $customer['targetId'] : null,
                'createdConversation' => $createdConversation,
                'createdLead' => $customer['createdLead'],
                'createdMessages' => $createdMessages,
                'deduplicatedMessages' => $deduplicatedMessages,
                'finalized' => $finalized,
            ];
            $audit = $this->em->getNewEntity('AutomationAudit');
            $audit->set([
                'name' => 'alibaba.sync.request ' . gmdate('H:i:s'),
                'eventType' => 'alibaba.sync.request',
                'requestId' => $requestId,
                'actorType' => 'agent',
                'actorId' => (string) ($agent->get('agentKey') ?: $agent->get('key') ?: $agent->getId()),
                'entityType' => 'ExternalConversation',
                'entityId' => $conversation->getId(),
                'result' => 'success',
                'details' => [
                    'mode' => $mode,
                    'count' => count($input->messages),
                    'jobId' => $jobId,
                    'accountHandle' => $accountHandle,
                    'payloadHash' => $payloadHash,
                    'matchMethod' => $customer['matchMethod'],
                    'response' => $response,
                ],
            ]);
            $this->kernel->save($audit);
            $tx->commit();
            return $response;
        } catch (\Throwable $e) {
            $tx->rollback();
            // A concurrent worker may have won the unique requestId race.
            // Only an identical completed request is safe to replay; every
            // other failure, including a mismatched requestId reuse, surfaces.
            $prior = $this->repo('AutomationAudit')->where(['requestId' => $requestId])->findOne();
            if ($prior && $this->sameReplay($prior, $jobId, $payloadHash)) {
                $details = $this->auditDetails($prior);
                $resp = $details['response'] ?? null;
                if ($resp instanceof \stdClass) {
                    return get_object_vars($resp);
                }
                if (is_array($resp)) {
                    return $resp;
                }
            }
            throw $e;
        }
    }

    private function validate(stdClass $input, Entity $agent): void
    {
        // This is a system integration boundary in a single-tenant CRM: the
        // connector has no current human user, so agent capability rather than
        // current-user ACL is the authorization boundary.
        if (!in_array('Alibaba', (array) ($agent->get('capabilities') ?? []), true)) {
            throw new Forbidden('Agent is not authorised for Alibaba synchronization.');
        }
        $this->requiredString($input, 'requestId', 64);
        $this->requiredString($input, 'jobId', 64);
        $this->requiredString($input, 'accountHandle', 191);
        if (!in_array((string) ($input->syncMode ?? ''), ['backfill', 'incremental'], true)) {
            throw new BadRequest('syncMode must be backfill or incremental.');
        }
        if (!isset($input->conversation) || !($input->conversation instanceof stdClass)) {
            throw new BadRequest('conversation.inquiryId is required.');
        }
        $this->requiredString($input->conversation, 'inquiryId', 191, 'conversation.');
        $this->optionalString($input->conversation, 'buyerExternalId', 191, 'conversation.');
        $this->optionalString($input->conversation, 'subject', 255, 'conversation.');
        $this->requiredString($input->conversation, 'buyerName', 255, 'conversation.');
        $this->optionalString($input->conversation, 'buyerEmail', 255, 'conversation.');
        $this->optionalString($input->conversation, 'buyerPhone', 100, 'conversation.');
        $this->optionalString($input->conversation, 'country', 100, 'conversation.');
        foreach (['createdAtRaw', 'updatedAtRaw'] as $field) {
            $this->optionalString($input->conversation, $field, 255, 'conversation.');
        }
        if (property_exists($input, 'finalBatch') && !is_bool($input->finalBatch)) {
            throw new BadRequest('finalBatch must be boolean.');
        }
        if (!isset($input->messages) || !is_array($input->messages) || count($input->messages) > self::MAX_MESSAGES) {
            throw new BadRequest('messages must contain at most ' . self::MAX_MESSAGES . ' entries.');
        }
        try {
            $bytes = strlen(json_encode($input, JSON_THROW_ON_ERROR));
        } catch (\JsonException) {
            throw new BadRequest('Input must be JSON serializable.');
        }
        if ($bytes > self::MAX_BATCH) {
            throw new BadRequest('Batch exceeds maximum size.');
        }
        foreach ($input->messages as $index => $message) {
            if (!($message instanceof stdClass)) {
                throw new BadRequest('messages[' . $index . '] must be an object.');
            }
            if (!isset($message->externalId) || !is_string($message->externalId) || trim($message->externalId) === '' || trim((string) ($message->body ?? '')) === '') {
                throw new BadRequest('messages[' . $index . '] externalId and body are required.');
            }
            $this->assertMaxLength($message->externalId, 191, 'messages[' . $index . '].externalId');
            if (strlen((string) $message->body) > self::MAX_BODY) {
                throw new BadRequest('Message body exceeds maximum size.');
            }
            if (!in_array((string) ($message->direction ?? ''), ['inbound', 'outbound'], true)
                || !in_array((string) ($message->timestampConfidence ?? ''), ['high', 'medium', 'low'], true)
                || !in_array((string) ($message->messageType ?? ''), ['initialInquiry', 'chat'], true)
                || !isset($message->sourceSequence)
                || !is_int($message->sourceSequence)
                || $message->sourceSequence < 1) {
                throw new BadRequest('messages[' . $index . '] has invalid synchronization metadata.');
            }
            $this->optionalString($message, 'sourceTimestampRaw', 255, 'messages[' . $index . '].');
            $this->optionalString($message, 'sentAt', 255, 'messages[' . $index . '].');
            $this->optionalString($message, 'senderName', 255, 'messages[' . $index . '].');
            $this->optionalString($message, 'senderExternalId', 191, 'messages[' . $index . '].');
            if (in_array((string) $message->timestampConfidence, ['high', 'medium'], true)) {
                $this->normaliseTime((string) ($message->sentAt ?? ''));
            }
        }
    }

    private function findChannel(string $accountHandle): Entity
    {
        $channel = $this->repo('ExternalChannel')
            ->where(['type' => 'Alibaba', 'accountHandle' => $accountHandle])
            ->forUpdate()->findOne();
        if ($channel) {
            if (!$channel->get('enabled')) {
                throw new Conflict('Alibaba channel is disabled.');
            }
            return $channel;
        }
        $channel = $this->em->getNewEntity('ExternalChannel');
        $channel->set([
            'name' => 'Alibaba · ' . $accountHandle,
            'type' => 'Alibaba',
            'accountHandle' => $accountHandle,
            'enabled' => true,
            'connectionStatus' => 'healthy',
        ]);
        try {
            $this->kernel->save($channel);
        } catch (\Throwable $e) {
            // A peer can insert this unique (type, accountHandle) row after
            // our locked miss.  Re-read it instead of exposing a raw database
            // unique-constraint error to the connector.
            $channel = $this->repo('ExternalChannel')
                ->where(['type' => 'Alibaba', 'accountHandle' => $accountHandle])
                ->forUpdate()->findOne();
            if (!$channel) {
                throw $e;
            }
            if (!$channel->get('enabled')) {
                throw new Conflict('Alibaba channel is disabled.');
            }
        }
        return $channel;
    }

    private function attachCustomer(Entity $conversation, Entity $identity, array $customer): void
    {
        $values = ['identityId' => $identity->getId(), 'needsManualMatch' => false];
        $field = match ($customer['targetType']) {
            'Account' => 'accountId',
            'Contact' => 'contactId',
            default => 'leadId',
        };
        $values[$field] = $customer['targetId'];
        $conversation->set($values);
    }

    private function refreshConversationState(Entity $conversation, stdClass $conversationInput): void
    {
        $conversation->set([
            'lastSourceSyncAt' => $this->kernel->now(),
            'sourceCreatedAtRaw' => (string) ($conversationInput->createdAtRaw ?? ''),
            'sourceUpdatedAtRaw' => (string) ($conversationInput->updatedAtRaw ?? ''),
        ]);
        $messages = iterator_to_array(
            $this->repo('ExternalMessage')->where(['conversationId' => $conversation->getId()])->find()
        );
        usort($messages, function (Entity $left, Entity $right): int {
            $sequence = ((int) $left->get('sourceSequence')) <=> ((int) $right->get('sourceSequence'));
            return $sequence !== 0 ? $sequence : strcmp((string) $left->get('sentAt'), (string) $right->get('sentAt'));
        });
        if (!$messages) {
            return;
        }
        $last = $messages[count($messages) - 1];
        $sentAt = (string) $last->get('sentAt');
        $inbound = $last->get('direction') === 'inbound';
        $updates = [
            'status' => $inbound ? 'pending' : 'replied',
            'unreadCount' => max(0, (int) ($conversationInput->unreadCount ?? 0)),
            'lastMessageAt' => $sentAt,
            'lastMessagePreview' => mb_substr((string) preg_replace('/\\s+/', ' ', (string) $last->get('body')), 0, 220),
        ];
        $updates[$inbound ? 'lastInboundAt' : 'lastOutboundAt'] = $sentAt;
        $conversation->set($updates);
    }

    private function lowConfidenceTime(stdClass $conversationInput, string $rawTimestamp, ?string $prevSentAt = null, int $sequence = 1): string
    {
        if ($rawTimestamp !== '') {
            try {
                return $this->normaliseTime($rawTimestamp);
            } catch (BadRequest) {
                // A low-confidence timestamp remains raw evidence; the CRM
                // ordering timestamp instead uses the explicit safe fallback.
            }
        }
        if ($prevSentAt !== null && trim($prevSentAt) !== '') {
            try {
                $prevDt = new \DateTimeImmutable($prevSentAt, new \DateTimeZone('UTC'));
                return $prevDt->modify('+1 second')->format('Y-m-d H:i:s');
            } catch (\Throwable) {
            }
        }
        $updated = (string) ($conversationInput->updatedAtRaw ?? '');
        if ($updated !== '') {
            try {
                $baseDt = new \DateTimeImmutable($this->normaliseTime($updated), new \DateTimeZone('UTC'));
                return $baseDt->modify('+' . max(0, $sequence) . ' seconds')->format('Y-m-d H:i:s');
            } catch (BadRequest|\Throwable) {
            }
        }
        return $this->kernel->now();
    }

    private function normaliseTime(string $value): string
    {
        $clean = trim($value);
        if ($clean === '') {
            throw new BadRequest('sentAt is required for high and medium confidence timestamps.');
        }
        try {
            $clean = preg_replace('/\s+Alibaba$/i', '', $clean);
            if (preg_match('/[+-]\d{2}:?\d{2}|Z$/', $clean)) {
                $dt = new \DateTimeImmutable($clean);
            } else {
                $dt = new \DateTimeImmutable($clean, new \DateTimeZone('Asia/Shanghai'));
            }
            return $dt->setTimezone(new \DateTimeZone('UTC'))->format('Y-m-d H:i:s');
        } catch (\Throwable) {
            throw new BadRequest('sentAt must be a valid timestamp.');
        }
    }

    private function existingConversationIdentity(Entity $conversation): ?Entity
    {
        $identityId = (string) $conversation->get('identityId');
        if ($identityId === '') {
            return null;
        }
        return $this->em->getEntityById('ExternalIdentity', $identityId) ?: null;
    }

    private function replayResponse(?Entity $prior, string $jobId, string $payloadHash): ?array
    {
        if (!$prior) {
            return null;
        }
        if (!$this->sameReplay($prior, $jobId, $payloadHash)) {
            throw new Conflict('requestId was already used with different job or payload.');
        }
        $details = $this->auditDetails($prior);
        $resp = $details['response'] ?? null;
        if ($resp instanceof \stdClass) {
            return get_object_vars($resp);
        }
        return is_array($resp) ? $resp : null;
    }

    private function sameReplay(Entity $prior, string $jobId, string $payloadHash): bool
    {
        $details = $this->auditDetails($prior);
        return isset($details['jobId'], $details['payloadHash'])
            && is_string($details['jobId'])
            && is_string($details['payloadHash'])
            && hash_equals($jobId, $details['jobId'])
            && hash_equals($payloadHash, $details['payloadHash']);
    }

    private function auditDetails(Entity $audit): array
    {
        $details = $audit->get('details');
        return $details instanceof stdClass ? get_object_vars($details) : (is_array($details) ? $details : []);
    }

    private function canonicalPayloadHash(stdClass $input): string
    {
        return hash('sha256', json_encode($this->canonicalValue($input), JSON_THROW_ON_ERROR | JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES));
    }

    private function canonicalValue(mixed $value): mixed
    {
        if ($value instanceof stdClass) {
            $value = get_object_vars($value);
        }
        if (!is_array($value)) {
            return $value;
        }
        $result = [];
        if (array_is_list($value)) {
            foreach ($value as $item) {
                $result[] = $this->canonicalValue($item);
            }
            return $result;
        }
        ksort($value, SORT_STRING);
        foreach ($value as $key => $item) {
            $result[$key] = $this->canonicalValue($item);
        }
        return $result;
    }

    private function requiredString(stdClass $input, string $field, int $maxLength, string $prefix = ''): string
    {
        if (!isset($input->$field) || !is_string($input->$field) || trim($input->$field) === '') {
            throw new BadRequest($prefix . $field . ' is required.');
        }
        $this->assertMaxLength($input->$field, $maxLength, $prefix . $field);
        return trim($input->$field);
    }

    private function optionalString(stdClass $input, string $field, int $maxLength, string $prefix = ''): void
    {
        if (!isset($input->$field)) {
            return;
        }
        if (!is_string($input->$field)) {
            throw new BadRequest($prefix . $field . ' must be a string.');
        }
        $this->assertMaxLength($input->$field, $maxLength, $prefix . $field);
    }

    private function assertMaxLength(string $value, int $maxLength, string $field): void
    {
        if (mb_strlen($value) > $maxLength) {
            throw new BadRequest($field . ' exceeds maximum length.');
        }
    }

    private function repo(string $type)
    {
        return $this->em->getRDBRepository($type);
    }
}
