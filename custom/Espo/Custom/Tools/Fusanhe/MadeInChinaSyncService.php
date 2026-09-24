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

/** MIC-only inbound history importer. No draft, task, or delivery side effects. */
final class MadeInChinaSyncService
{
    public const MAX_MESSAGES = 100;
    public const MAX_BODY = 200000;
    public const MAX_BATCH = 2000000;
    public const MAX_ATTACHMENTS = 20;

    public function __construct(
        private EntityManager $em,
        private ServiceKernel $kernel,
        private IdentityService $identityService,
    ) {}

    public function sync(stdClass $input, Entity $agent): array
    {
        $this->validate($input, $agent);
        $requestId = trim($input->requestId);
        $jobId = trim($input->jobId);
        $accountHandle = trim($input->accountHandle);
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

            $conversationInput = $input->conversation;
            $sourceId = trim($conversationInput->sourceId);
            $channel = $this->findChannel($accountHandle);
            $conversation = $this->repo('ExternalConversation')
                ->where(['channelId' => $channel->getId(), 'externalId' => $sourceId])
                ->forUpdate()->findOne();
            $createdConversation = !$conversation;
            if (!$conversation) {
                $conversation = $this->em->getNewEntity('ExternalConversation');
                $conversation->set([
                    'name' => 'Made-in-China 询盘 ' . $sourceId,
                    'channelId' => $channel->getId(),
                    'externalId' => $sourceId,
                    'externalUserId' => trim($conversationInput->buyerExternalId),
                    'subject' => (string) ($conversationInput->subject ?? ''),
                    'country' => (string) ($conversationInput->country ?? ''),
                    'status' => 'new',
                    'unreadCount' => 0,
                    'needsManualMatch' => false,
                ]);
                $this->kernel->save($conversation);
            }

            $buyerId = trim($conversationInput->buyerExternalId);
            $this->refreshConversationSourceMetadata($conversation, $conversationInput, $buyerId);
            $buyerName = trim((string) $conversationInput->buyerName);
            $placeholder = (bool) $conversationInput->buyerNameIsPlaceholder;
            if ($placeholder) {
                $buyerName = 'MIC 买家 ' . $buyerId;
            }
            $profile = [
                'displayName' => $buyerName,
                'emailAddress' => '',
                'phoneNumber' => '',
                'country' => trim((string) ($conversationInput->country ?? '')),
                'buyerNameIsPlaceholder' => $placeholder,
            ];
            $identity = $this->existingConversationIdentity($conversation);
            if ($identity === null) {
                try {
                    [$identity,] = $this->identityService->resolveIdentity(
                        'MadeInChina', $accountHandle, $buyerId, '', '', $sourceId, $profile,
                    );
                } catch (\Throwable $e) {
                    if (!$this->isDuplicateKeyViolation($e)) {
                        throw $e;
                    }
                    $identityKey = $this->identityService->buildIdentityKey(
                        'MadeInChina', $accountHandle, $buyerId, '', '', $sourceId,
                    );
                    $identity = $this->repo('ExternalIdentity')
                        ->where(['identityKey' => $identityKey])->forUpdate()->findOne();
                    if (!$identity) {
                        throw $e;
                    }
                    if ((string) $identity->get('channelType') !== 'MadeInChina'
                        || (string) $identity->get('channelAccountId') !== $accountHandle
                        || (string) $identity->get('externalUserId') !== $buyerId) {
                        throw new Conflict('MIC buyer identity race did not resolve to the expected account.');
                    }
                }
            } else {
                if ((string) $identity->get('channelAccountId') !== $accountHandle
                    || (string) $identity->get('externalUserId') !== $buyerId) {
                    throw new Conflict('MIC conversation source ID is already bound to a different buyer identity.');
                }
            }
            $this->identityService->refreshMadeInChinaProfile($identity, $buyerId, $profile);
            $customer = $this->identityService->resolveMadeInChinaCustomer($identity, $sourceId, $buyerId);
            $this->attachCustomer($conversation, $identity, $customer);
            $this->kernel->save($conversation);

            $createdMessages = 0;
            $deduplicatedMessages = 0;
            foreach ($input->messages as $messageIndex => $messageInput) {
                $externalId = trim($messageInput->externalId);
                $direction = (string) $messageInput->direction;
                $body = (string) $messageInput->body;
                $hashInput = json_encode(
                    ['MadeInChina', $accountHandle, $sourceId, $direction, $externalId, $body],
                    JSON_THROW_ON_ERROR | JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES,
                );
                $hash = hash('sha256', $hashInput);
                $existing = $this->repo('ExternalMessage')
                    ->where(['conversationId' => $conversation->getId(), 'externalId' => $externalId])
                    ->forUpdate()->findOne();
                if ($existing) {
                    if (!hash_equals((string) $existing->get('contentHash'), $hash)) {
                        throw new Conflict('MIC source message ID was replayed with different content.');
                    }
                    $this->refreshExistingMessageSourceMetadata($existing, $messageInput, $messageIndex);
                    $deduplicatedMessages++;
                    continue;
                }
                $sameContent = $this->repo('ExternalMessage')
                    ->where(['conversationId' => $conversation->getId(), 'contentHash' => $hash])->findOne();
                if ($sameContent) {
                    $this->refreshExistingMessageSourceMetadata($sameContent, $messageInput, $messageIndex);
                    $deduplicatedMessages++;
                    continue;
                }

                $sentAt = $this->messageTime($messageInput, $conversation);
                $attachmentMetadata = property_exists($messageInput, 'attachmentMetadata')
                    ? $this->validateAttachmentMetadata($messageInput->attachmentMetadata, 'messages[' . $messageIndex . '].attachmentMetadata')
                    : null;
                $senderName = trim((string) ($messageInput->senderName ?? ''));
                if ($senderName === '') {
                    $senderName = $direction === 'inbound' ? ($buyerName !== '' ? $buyerName : '买家') : '我方客服';
                }
                $senderExternalId = trim((string) ($messageInput->senderExternalId ?? ''));
                $rawPayload = [
                    'source' => 'MadeInChina',
                    'externalId' => $externalId,
                    'senderNameHash' => hash('sha256', $senderName),
                    'senderExternalIdHash' => hash('sha256', $senderExternalId),
                ];
                if ($attachmentMetadata !== null) {
                    $rawPayload['attachmentMetadataHash'] = $this->attachmentMetadataHash($attachmentMetadata);
                }
                $message = $this->em->getNewEntity('ExternalMessage');
                $message->set([
                    'name' => ($direction === 'inbound' ? 'IN ' : 'OUT ') . $externalId,
                    'conversationId' => $conversation->getId(),
                    'externalId' => $externalId,
                    'direction' => $direction,
                    'senderName' => $senderName,
                    'senderExternalId' => $senderExternalId,
                    'sentAt' => $sentAt,
                    'body' => $body,
                    'attachmentMetadata' => $attachmentMetadata,
                    'deliveryStatus' => $direction === 'outbound' ? 'sent' : 'received',
                    'contentHash' => $hash,
                    'sourceTimestampRaw' => (string) ($messageInput->sourceTimestampRaw ?? ''),
                    'timestampConfidence' => (string) $messageInput->timestampConfidence,
                    'sourceSequence' => $messageInput->sourceSequence,
                    'messageType' => (string) $messageInput->messageType,
                    'rawPayload' => $rawPayload,
                ]);
                $this->kernel->save($message);
                $createdMessages++;
            }

            $finalized = (string) $input->syncMode === 'incremental' || (bool) $input->finalBatch;
            if ($finalized) {
                $this->refreshConversationState($conversation);
                if ((string) $input->syncMode === 'backfill' && $input->finalBatch) {
                    $conversation->set('backfillCompletedAt', $this->kernel->now());
                }
                $this->kernel->save($conversation);
            }

            $response = [
                'accepted' => true,
                'requestId' => $requestId,
                'conversationId' => $conversation->getId(),
                'identityId' => $identity->getId(),
                'leadId' => $customer['targetId'],
                'createdConversation' => $createdConversation,
                'createdLead' => $customer['createdLead'],
                'createdMessages' => $createdMessages,
                'deduplicatedMessages' => $deduplicatedMessages,
                'finalized' => $finalized,
            ];
            $audit = $this->em->getNewEntity('AutomationAudit');
            $audit->set([
                'name' => 'madeInChina.sync.request ' . gmdate('H:i:s'),
                'eventType' => 'madeInChina.sync.request',
                'requestId' => $requestId,
                'actorType' => 'agent',
                'actorId' => (string) ($agent->get('agentKey') ?: $agent->get('key') ?: $agent->getId()),
                'entityType' => 'ExternalConversation',
                'entityId' => $conversation->getId(),
                'result' => 'success',
                'details' => [
                    'jobId' => $jobId,
                    'accountHandle' => $accountHandle,
                    'payloadHash' => $payloadHash,
                    'messageCount' => count($input->messages),
                    'response' => $response,
                ],
            ]);
            $this->kernel->save($audit);
            $tx->commit();
            return $response;
        } catch (\Throwable $e) {
            $tx->rollback();
            $prior = $this->repo('AutomationAudit')->where(['requestId' => $requestId])->findOne();
            if ($prior && $this->sameReplay($prior, $jobId, $payloadHash)) {
                $details = $this->auditDetails($prior);
                $response = $details['response'] ?? null;
                $response = $this->normalizeAcceptedResponse($response);
                if ($response !== null) return $response;
            }
            throw $e;
        }
    }

    private function validate(stdClass $input, Entity $agent): void
    {
        if (!in_array('MadeInChina', (array) ($agent->get('capabilities') ?? []), true)) {
            throw new Forbidden('Agent is not authorised for Made-in-China synchronization.');
        }
        $this->allowOnly($input, ['requestId', 'jobId', 'accountHandle', 'syncMode', 'batchNo', 'finalBatch', 'conversation', 'messages']);
        $this->requiredString($input, 'requestId', 64);
        $this->requiredString($input, 'jobId', 128);
        $accountHandle = $this->requiredString($input, 'accountHandle', 191);
        if (!in_array((string) ($input->syncMode ?? ''), ['backfill', 'incremental'], true)) {
            throw new BadRequest('syncMode must be backfill or incremental.');
        }
        if (!isset($input->batchNo) || !is_int($input->batchNo) || $input->batchNo < 1) {
            throw new BadRequest('batchNo must be a positive integer.');
        }
        if (!isset($input->finalBatch) || !is_bool($input->finalBatch)) {
            throw new BadRequest('finalBatch must be boolean.');
        }
        if (!isset($input->conversation) || !($input->conversation instanceof stdClass)) {
            throw new BadRequest('conversation.sourceId is required.');
        }
        $this->allowOnly($input->conversation, ['sourceId', 'buyerExternalId', 'buyerName', 'buyerNameIsPlaceholder', 'subject', 'country', 'unreadCount']);
        $this->requiredString($input->conversation, 'sourceId', 191, 'conversation.');
        $this->requiredString($input->conversation, 'buyerExternalId', 191, 'conversation.');
        if (mb_strlen('MadeInChina|' . $accountHandle . '|uid:' . trim($input->conversation->buyerExternalId)) > 191) {
            throw new BadRequest('accountHandle and buyerExternalId exceed the identity key limit.');
        }
        $this->requiredString($input->conversation, 'buyerName', 255, 'conversation.');
        $this->optionalString($input->conversation, 'subject', 255, 'conversation.');
        $this->optionalString($input->conversation, 'country', 100, 'conversation.');
        if (!isset($input->conversation->buyerNameIsPlaceholder) || !is_bool($input->conversation->buyerNameIsPlaceholder)) {
            throw new BadRequest('conversation.buyerNameIsPlaceholder must be boolean.');
        }
        if ($input->conversation->buyerNameIsPlaceholder
            && trim($input->conversation->buyerName) !== 'MIC 买家 ' . trim($input->conversation->buyerExternalId)) {
            throw new BadRequest('Placeholder buyerName must include the stable MIC buyer ID.');
        }
        if (!isset($input->messages) || !is_array($input->messages) || count($input->messages) > self::MAX_MESSAGES) {
            throw new BadRequest('messages must contain at most ' . self::MAX_MESSAGES . ' entries.');
        }
        try {
            if (strlen(json_encode($input, JSON_THROW_ON_ERROR)) > self::MAX_BATCH) {
                throw new BadRequest('Batch exceeds maximum size.');
            }
        } catch (\JsonException) {
            throw new BadRequest('Input must be JSON serializable.');
        }
        foreach ($input->messages as $index => $message) {
            if (!($message instanceof stdClass)) {
                throw new BadRequest('messages[' . $index . '] must be an object.');
            }
            $this->allowOnly($message, ['externalId', 'sourceSequence', 'direction', 'messageType', 'body', 'sourceTimestampRaw', 'timestampConfidence', 'sentAt', 'senderName', 'senderExternalId', 'attachmentMetadata']);
            $this->requiredString($message, 'externalId', 191, 'messages[' . $index . '].');
            $body = $this->requiredString($message, 'body', self::MAX_BODY, 'messages[' . $index . '].');
            if (strlen($body) > self::MAX_BODY) {
                throw new BadRequest('Message body exceeds maximum size.');
            }
            if (!isset($message->sourceSequence) || !is_int($message->sourceSequence) || $message->sourceSequence < 1
                || !in_array((string) ($message->direction ?? ''), ['inbound', 'outbound'], true)
                || !in_array((string) ($message->messageType ?? ''), ['initialInquiry', 'chat'], true)
                || !in_array((string) ($message->timestampConfidence ?? ''), ['high', 'medium', 'low'], true)) {
                throw new BadRequest('messages[' . $index . '] has invalid synchronization metadata.');
            }
            $this->optionalString($message, 'sourceTimestampRaw', 255, 'messages[' . $index . '].');
            $this->optionalString($message, 'sentAt', 255, 'messages[' . $index . '].');
            $this->optionalString($message, 'senderName', 255, 'messages[' . $index . '].');
            $this->optionalString($message, 'senderExternalId', 191, 'messages[' . $index . '].');
            if (property_exists($message, 'attachmentMetadata')) {
                $this->validateAttachmentMetadata($message->attachmentMetadata, 'messages[' . $index . '].attachmentMetadata');
            }
            if (in_array($message->timestampConfidence, ['high', 'medium'], true)) {
                $this->normaliseTime((string) ($message->sentAt ?? $message->sourceTimestampRaw ?? ''));
            }
        }
        if ($accountHandle === '') {
            throw new BadRequest('accountHandle is required.');
        }
    }

    private function findChannel(string $accountHandle): Entity
    {
        // Do a non-locking miss check first. Locking an absent unique row can
        // take competing gap locks; locking the winner below serializes all
        // source/identity writes for this account after it exists.
        $channel = $this->repo('ExternalChannel')->where(['type' => 'MadeInChina', 'accountHandle' => $accountHandle])->findOne();
        if ($channel) {
            $channel = $this->repo('ExternalChannel')->where(['type' => 'MadeInChina', 'accountHandle' => $accountHandle])->forUpdate()->findOne();
            if (!$channel) {
                throw new Conflict('Made-in-China channel disappeared during synchronization.');
            }
            if (!$channel->get('enabled')) {
                throw new Conflict('Made-in-China channel is disabled.');
            }
            return $channel;
        }
        $channel = $this->em->getNewEntity('ExternalChannel');
        $channel->set(['name' => 'Made-in-China · ' . $accountHandle, 'type' => 'MadeInChina', 'accountHandle' => $accountHandle, 'enabled' => true, 'connectionStatus' => 'healthy']);
        try {
            $this->kernel->save($channel);
        } catch (\Throwable $e) {
            if (!$this->isDuplicateKeyViolation($e)) {
                throw $e;
            }
            $channel = $this->repo('ExternalChannel')->where(['type' => 'MadeInChina', 'accountHandle' => $accountHandle])->forUpdate()->findOne();
            if (!$channel) {
                throw $e;
            }
            if (!$channel->get('enabled')) {
                throw new Conflict('Made-in-China channel is disabled.');
            }
        }
        return $channel;
    }

    private function isDuplicateKeyViolation(\Throwable $error): bool
    {
        for ($current = $error; $current !== null; $current = $current->getPrevious()) {
            if ($current instanceof \PDOException) {
                $info = $current->errorInfo ?? [];
                if ((string) ($info[0] ?? '') === '23000' && (int) ($info[1] ?? 0) === 1062) {
                    return true;
                }
            }
            if (preg_match('/SQLSTATE\[23000\].*(?:duplicate entry|duplicate key)/i', $current->getMessage())) {
                return true;
            }
        }
        return false;
    }

    private function attachCustomer(Entity $conversation, Entity $identity, array $customer): void
    {
        $field = match ($customer['targetType']) {
            'Account' => 'accountId',
            'Contact' => 'contactId',
            default => 'leadId',
        };
        $conversation->set(['identityId' => $identity->getId(), $field => $customer['targetId'], 'needsManualMatch' => false]);
    }

    /** Refresh source-owned conversation metadata after stable identity validation. */
    private function refreshConversationSourceMetadata(Entity $conversation, stdClass $conversationInput, string $buyerId): void
    {
        $updates = ['externalUserId' => $buyerId];
        foreach (['subject', 'country'] as $field) {
            if (property_exists($conversationInput, $field)) {
                $updates[$field] = (string) $conversationInput->$field;
            }
        }
        $conversation->set($updates);
    }

    private function refreshConversationState(Entity $conversation): void
    {
        $conversation->set('lastSourceSyncAt', $this->kernel->now());
        $messages = iterator_to_array($this->repo('ExternalMessage')->where(['conversationId' => $conversation->getId()])->find());
        usort($messages, static function (Entity $left, Entity $right): int {
            $sequence = ((int) $left->get('sourceSequence')) <=> ((int) $right->get('sourceSequence'));
            return $sequence !== 0 ? $sequence : strcmp((string) $left->get('sentAt'), (string) $right->get('sentAt'));
        });
        if (!$messages) {
            return;
        }
        $last = $messages[count($messages) - 1];
        $sentAt = (string) $last->get('sentAt');
        $inbound = $last->get('direction') === 'inbound';
        $lastDirectionField = $inbound ? 'lastInboundAt' : 'lastOutboundAt';
        $conversation->set([
            'status' => $inbound ? 'pending' : 'replied',
            'lastMessageAt' => $sentAt,
            'lastMessagePreview' => mb_substr((string) preg_replace('/\s+/', ' ', (string) $last->get('body')), 0, 220),
            $lastDirectionField => $sentAt,
        ]);
    }

    private function existingConversationIdentity(Entity $conversation): ?Entity
    {
        $id = (string) $conversation->get('identityId');
        return $id === '' ? null : ($this->em->getEntityById('ExternalIdentity', $id) ?: null);
    }

    private function replayResponse(?Entity $prior, string $jobId, string $hash): ?array
    {
        if (!$prior) return null;
        if (!$this->sameReplay($prior, $jobId, $hash)) throw new Conflict('requestId was already used with different job or payload.');
        $response = $this->auditDetails($prior)['response'] ?? null;
        return $this->normalizeAcceptedResponse($response);
    }

    private function normalizeAcceptedResponse(mixed $response): ?array
    {
        if ($response instanceof stdClass) $response = get_object_vars($response);
        if (!is_array($response)) return null;
        // Successful legacy audits may predate the explicit bridge ack field.
        $response['accepted'] = true;
        return $response;
    }

    private function sameReplay(Entity $audit, string $jobId, string $hash): bool
    {
        $details = $this->auditDetails($audit);
        return isset($details['jobId'], $details['payloadHash'])
            && hash_equals($jobId, (string) $details['jobId'])
            && hash_equals($hash, (string) $details['payloadHash']);
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
        if ($value instanceof stdClass) $value = get_object_vars($value);
        if (!is_array($value)) return $value;
        if (array_is_list($value)) return array_map(fn($item) => $this->canonicalValue($item), $value);
        ksort($value, SORT_STRING);
        foreach ($value as $key => $item) $value[$key] = $this->canonicalValue($item);
        return $value;
    }

    private function allowOnly(stdClass $input, array $allowed): void
    {
        foreach (array_keys(get_object_vars($input)) as $key) {
            if (!in_array($key, $allowed, true)) throw new BadRequest('Unsupported synchronization field: ' . $key . '.');
        }
    }

    private function requiredString(stdClass $input, string $field, int $limit, string $prefix = ''): string
    {
        if (!isset($input->$field) || !is_string($input->$field) || trim($input->$field) === '') throw new BadRequest($prefix . $field . ' is required.');
        if (mb_strlen($input->$field) > $limit) throw new BadRequest($prefix . $field . ' exceeds maximum length.');
        return trim($input->$field);
    }

    private function optionalString(stdClass $input, string $field, int $limit, string $prefix = ''): void
    {
        if (!property_exists($input, $field)) return;
        if (!is_string($input->$field) || mb_strlen($input->$field) > $limit) throw new BadRequest($prefix . $field . ' is invalid or exceeds maximum length.');
    }

    private function validateAttachmentMetadata(mixed $value, string $field): array
    {
        if (!($value instanceof stdClass)) {
            throw new BadRequest($field . ' must be an object.');
        }
        $this->allowOnly($value, ['items']);
        if (!isset($value->items) || !is_array($value->items)) {
            throw new BadRequest($field . '.items must be an array.');
        }
        if (count($value->items) > self::MAX_ATTACHMENTS) {
            throw new BadRequest($field . '.items must contain at most ' . self::MAX_ATTACHMENTS . ' entries.');
        }

        $items = [];
        foreach ($value->items as $index => $item) {
            $itemField = $field . '.items[' . $index . ']';
            if (!($item instanceof stdClass)) {
                throw new BadRequest($itemField . ' must be an object.');
            }
            $this->allowOnly($item, ['name', 'mediaType', 'size']);
            $name = $this->requiredString($item, 'name', 255, $itemField . '.');
            if (!property_exists($item, 'mediaType') || (!is_string($item->mediaType) && $item->mediaType !== null)) {
                throw new BadRequest($itemField . '.mediaType must be a string or null.');
            }
            if (is_string($item->mediaType) && mb_strlen($item->mediaType) > 127) {
                throw new BadRequest($itemField . '.mediaType exceeds maximum length.');
            }
            if (!property_exists($item, 'size') || (!is_int($item->size) && $item->size !== null) || (is_int($item->size) && $item->size < 0)) {
                throw new BadRequest($itemField . '.size must be a non-negative integer or null.');
            }
            $mediaType = $item->mediaType;
            foreach ([$name, $mediaType] as $text) {
                $unsafeTextPattern = '/(?:[a-z][a-z0-9+.-]*:\/\/|data:|javascript:|\/\/|(?:^|[\s(])www\.(?:[a-z0-9-]+\.)+[a-z]{2,}(?:[\/?#:][^\s]*)?(?:$|\s)|(?:^|[\s(])(?:[a-z0-9-]+\.)+[a-z]{2,}[\/?#:][^\s]*|(?:api[_-]?key|access[_-]?token|refresh[_-]?token|client[_-]?secret|token|secret|password|authorization)\s*=\s*\S+|(?:^|\s)bearer\s+\S+)/i';
                if (is_string($text) && preg_match($unsafeTextPattern, $text)) {
                    throw new BadRequest($itemField . ' must not contain URLs or token material.');
                }
            }
            $items[] = ['name' => $name, 'mediaType' => $mediaType, 'size' => $item->size];
        }

        return ['items' => $items];
    }

    /** Refresh source-owned metadata on a content-identical message replay. */
    private function refreshExistingMessageSourceMetadata(Entity $message, stdClass $input, int $messageIndex): void
    {
        $updates = [];
        $rawPayload = $message->get('rawPayload');
        if ($rawPayload instanceof stdClass) {
            $rawPayload = get_object_vars($rawPayload);
        }
        $rawPayload = is_array($rawPayload) ? $rawPayload : [];
        $originalRawPayload = $rawPayload;

        $senderName = property_exists($input, 'senderName') ? trim((string) $input->senderName) : '';
        $sourceSenderHash = $rawPayload['senderNameHash'] ?? null;
        $currentSenderName = trim((string) $message->get('senderName'));
        // A source hash records per-field provenance. If it no longer matches,
        // a CRM user has edited the sender and the importer preserves that value.
        if ($senderName !== '' && is_string($sourceSenderHash)
            && hash_equals($sourceSenderHash, hash('sha256', $currentSenderName))
            && $senderName !== $currentSenderName) {
            $updates['senderName'] = $senderName;
            $rawPayload['senderNameHash'] = hash('sha256', $senderName);
        }

        $senderExternalId = property_exists($input, 'senderExternalId') ? trim((string) $input->senderExternalId) : null;
        $sourceSenderExternalIdHash = $rawPayload['senderExternalIdHash'] ?? null;
        $currentSenderExternalId = trim((string) $message->get('senderExternalId'));
        $senderExternalIdIsSourceOwned = is_string($sourceSenderExternalIdHash)
            ? hash_equals($sourceSenderExternalIdHash, hash('sha256', $currentSenderExternalId))
            : (($rawPayload['source'] ?? null) === 'MadeInChina');
        if ($senderExternalId !== null && $senderExternalIdIsSourceOwned
            && $senderExternalId !== $currentSenderExternalId) {
            $updates['senderExternalId'] = $senderExternalId;
            $rawPayload['senderExternalIdHash'] = hash('sha256', $senderExternalId);
        }

        $incomingSequence = (int) $input->sourceSequence;
        if ($incomingSequence !== (int) $message->get('sourceSequence')) {
            $updates['sourceSequence'] = $incomingSequence;
        }
        $incomingMessageType = (string) $input->messageType;
        if ($incomingMessageType !== (string) $message->get('messageType')) {
            $updates['messageType'] = $incomingMessageType;
        }

        $incomingConfidence = (string) $input->timestampConfidence;
        $currentConfidence = (string) ($message->get('timestampConfidence') ?: 'low');
        $timestampText = property_exists($input, 'sentAt') ? trim((string) $input->sentAt) : '';
        $sourceTimestampRaw = property_exists($input, 'sourceTimestampRaw') ? trim((string) $input->sourceTimestampRaw) : '';
        if ($timestampText === '') {
            $timestampText = $sourceTimestampRaw;
        }
        if ($timestampText !== '' && $this->confidenceRank($incomingConfidence) >= $this->confidenceRank($currentConfidence)) {
            try {
                $incomingSentAt = $this->normaliseTime($timestampText);
                if ($incomingSentAt !== (string) $message->get('sentAt')) {
                    $updates['sentAt'] = $incomingSentAt;
                }
                if ($incomingConfidence !== $currentConfidence) {
                    $updates['timestampConfidence'] = $incomingConfidence;
                }
                if (property_exists($input, 'sourceTimestampRaw')
                    && (string) $input->sourceTimestampRaw !== (string) $message->get('sourceTimestampRaw')) {
                    $updates['sourceTimestampRaw'] = (string) $input->sourceTimestampRaw;
                }
            } catch (BadRequest $e) {
                if ($incomingConfidence !== 'low') {
                    throw $e;
                }
                // An invalid low-confidence timestamp is retained as raw evidence only;
                // preserve the previous normalized CRM time.
            }
        }

        if (property_exists($input, 'attachmentMetadata')) {
            $incomingAttachmentMetadata = $this->validateAttachmentMetadata(
                $input->attachmentMetadata,
                'messages[' . $messageIndex . '].attachmentMetadata',
            );
            $incomingItems = $incomingAttachmentMetadata['items'];
            $currentAttachmentMetadata = $this->canonicalValue($message->get('attachmentMetadata'));
            $currentItems = is_array($currentAttachmentMetadata) && is_array($currentAttachmentMetadata['items'] ?? null)
                ? $currentAttachmentMetadata['items']
                : [];
            $sourceAttachmentHash = $rawPayload['attachmentMetadataHash'] ?? null;
            $currentAttachmentHash = is_array($currentAttachmentMetadata) && array_key_exists('items', $currentAttachmentMetadata)
                ? $this->attachmentMetadataHash($currentAttachmentMetadata)
                : null;
            $attachmentIsSourceOwned = ($currentItems === [] && !is_string($sourceAttachmentHash)) || (
                is_string($sourceAttachmentHash)
                && is_string($currentAttachmentHash)
                && hash_equals($sourceAttachmentHash, $currentAttachmentHash)
            );
            // Empty source observations never downgrade known attachment data.
            if ($attachmentIsSourceOwned && ($incomingItems !== [] || $currentItems === [])) {
                if ($currentAttachmentMetadata !== $this->canonicalValue($incomingAttachmentMetadata)) {
                    $updates['attachmentMetadata'] = $incomingAttachmentMetadata;
                }
                $rawPayload['attachmentMetadataHash'] = $this->attachmentMetadataHash($incomingAttachmentMetadata);
            }
        }

        if ($rawPayload !== $originalRawPayload) {
            $updates['rawPayload'] = $rawPayload;
        }
        if ($updates) {
            $message->set($updates);
            $this->kernel->save($message);
        }
    }

    private function attachmentMetadataHash(array $metadata): string
    {
        return hash('sha256', json_encode(
            $this->canonicalValue($metadata),
            JSON_THROW_ON_ERROR | JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES,
        ));
    }

    private function confidenceRank(string $confidence): int
    {
        return match ($confidence) {
            'high' => 3,
            'medium' => 2,
            'low' => 1,
            default => 0,
        };
    }

    private function normaliseTime(string $value): string
    {
        $clean = trim($value);
        if ($clean === '') throw new BadRequest('sentAt is required for high and medium confidence timestamps.');
        try {
            $dt = preg_match('/[+-]\d{2}:?\d{2}|Z$/', $clean)
                ? new DateTimeImmutable($clean)
                : new DateTimeImmutable($clean, new DateTimeZone('Asia/Shanghai'));
            return $dt->setTimezone(new DateTimeZone('UTC'))->format('Y-m-d H:i:s');
        } catch (\Throwable) {
            throw new BadRequest('sentAt must be a valid timestamp.');
        }
    }

    private function messageTime(stdClass $message, Entity $conversation): string
    {
        $raw = trim((string) ($message->sentAt ?? $message->sourceTimestampRaw ?? ''));
        try {
            return $this->normaliseTime($raw);
        } catch (BadRequest $e) {
            if ((string) $message->timestampConfidence !== 'low') {
                throw $e;
            }
            $sequence = max(1, (int) $message->sourceSequence);
            $base = (string) $conversation->get('sourceUpdatedAtRaw');
            try {
                $time = $base !== '' ? $this->normaliseTime($base) : $this->kernel->now();
            } catch (BadRequest) {
                $time = $this->kernel->now();
            }
            return (new DateTimeImmutable($time, new DateTimeZone('UTC')))
                ->modify('+' . $sequence . ' seconds')->format('Y-m-d H:i:s');
        }
    }

    private function repo(string $type)
    {
        return $this->em->getRDBRepository($type);
    }
}
