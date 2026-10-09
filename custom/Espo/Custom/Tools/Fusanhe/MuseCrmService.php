<?php

namespace Espo\Custom\Tools\Fusanhe;

use DateTimeImmutable;
use DateTimeZone;
use Espo\Core\Exceptions\BadRequest;
use Espo\Core\Exceptions\Conflict;
use Espo\Core\Exceptions\Forbidden;
use Espo\Core\Exceptions\NotFound;
use Espo\ORM\Entity;
use Espo\ORM\EntityManager;
use stdClass;

/**
 * CRM-side boundary for a future Muse Code MCP server.
 *
 * This class deliberately exposes prospect/activity operations instead of
 * generic Espo CRUD. Muse can write provenance and message history, while
 * approval, outbound tasks and platform connectors remain separate services.
 */
final class MuseCrmService
{
    private const AGENT_CAPABILITY = 'MuseCRM';
    private const SOURCE_SYSTEM = 'Muse';
    private const CHANNEL_TYPES = ['Alibaba', 'MadeInChina', 'Website', 'Email', 'WhatsApp', 'Other'];
    private const POLICIES = ['unknown', 'allowed', 'optedOut', 'restricted'];
    private const DIRECTIONS = ['inbound', 'outbound'];
    private const DELIVERY_STATUSES = ['queued', 'sending', 'sent', 'delivered', 'failed', 'mockSent', 'received'];
    private const MAX_BODY = 20000;
    private const MAX_NOTE = 10000;

    public function __construct(
        private EntityManager $em,
        private ServiceKernel $kernel,
    ) {}

    public function assertCapability(Entity $agent): void
    {
        if (!in_array(self::AGENT_CAPABILITY, (array) ($agent->get('capabilities') ?? []), true)) {
            throw new Forbidden('Agent is not authorised for Muse CRM operations.');
        }
    }

    public function searchProspects(stdClass $input, Entity $agent): array
    {
        $this->assertCapability($agent);
        $sourceId = $this->optionalString($input, 'sourceId', 191);
        $email = $this->optionalString($input, 'email', 255);
        $phone = $this->optionalString($input, 'phone', 100);
        $name = $this->optionalString($input, 'name', 255);
        if ($sourceId === '' && $email === '' && $phone === '' && $name === '') {
            throw new BadRequest('At least one search field is required.');
        }
        $limit = max(1, min(25, (int) ($input->limit ?? 10)));
        $rows = [];
        $seen = [];
        $queries = [];
        if ($sourceId !== '') {
            $queries[] = ['fusanheSourceSystem' => self::SOURCE_SYSTEM, 'fusanheSourceId' => $sourceId];
        }
        if ($email !== '') {
            $queries[] = ['emailAddress' => $email];
        }
        if ($phone !== '') {
            $queries[] = ['phoneNumber' => $phone];
        }
        if ($name !== '') {
            $queries[] = ['name*' => '%' . $name . '%'];
        }
        foreach ($queries as $where) {
            foreach ($this->repo('Lead')->where($where)->limit(0, $limit)->find() as $lead) {
                if (isset($seen[$lead->getId()])) {
                    continue;
                }
                $seen[$lead->getId()] = true;
                $rows[] = $this->leadProjection($lead);
                if (count($rows) >= $limit) {
                    break 2;
                }
            }
        }
        return ['prospects' => $rows, 'count' => count($rows)];
    }

    public function upsertProspect(stdClass $input, Entity $agent): array
    {
        $this->assertCapability($agent);
        $sourceId = $this->requiredString($input, 'sourceId', 191);
        $sourceAccount = $this->optionalString($input, 'sourceAccount', 191) ?: 'default';
        $policy = $this->policy($input->contactPolicy ?? 'unknown');
        $sourceUrl = $this->optionalString($input, 'sourceUrl', 255);
        $campaignKey = $this->optionalString($input, 'campaignKey', 191);
        $profile = $this->profile($input);
        if ($profile['displayName'] === '' && $profile['company'] === '' && $profile['email'] === '') {
            throw new BadRequest('displayName, company or email is required.');
        }

        $tx = $this->em->getTransactionManager();
        $tx->start();
        try {
            $identityKey = $this->identityKey($sourceAccount, $sourceId);
            $identity = $this->repo('ExternalIdentity')->forUpdate()->where(['identityKey' => $identityKey])->findOne();
            $identityCreated = false;
            $now = $this->kernel->now();
            if (!$identity) {
                $identity = $this->em->getNewEntity('ExternalIdentity');
                $identity->set([
                    'name' => $profile['displayName'] ?: ($profile['company'] ?: 'Muse prospect ' . $sourceId),
                    'identityKey' => $identityKey,
                    'channelType' => 'Other',
                    'channelAccountId' => $this->stableMuseAccountId($sourceAccount),
                    'externalUserId' => $sourceId,
                    'linkStatus' => 'unlinked',
                    'firstSeenAt' => $now,
                    'lastSeenAt' => $now,
                ]);
                if ($profile['displayName'] !== '') {
                    $identity->set('displayName', $profile['displayName']);
                }
                $identityCreated = true;
            } else {
                $identity->set(['lastSeenAt' => $now]);
            }
            foreach (['displayName' => 'displayName', 'emailAddress' => 'email', 'phoneNumber' => 'phone', 'country' => 'country'] as $identityField => $profileField) {
                if ($profile[$profileField] !== '' && trim((string) $identity->get($identityField)) === '') {
                    $identity->set($identityField, $profile[$profileField]);
                }
            }
            $this->kernel->save($identity);

            $target = $this->linkedTarget($identity);
            $targetType = $target['type'];
            $targetEntity = $target['entity'];
            if ($targetEntity) {
                // A confirmed human/customer match is authoritative. Muse can
                // refresh the identity profile but may not overwrite the
                // linked Account, Contact or Lead.
                $response = $this->prospectResponse($identity, $targetEntity, $targetType, true, $identityCreated, $policy);
                $this->audit($agent, 'muse.prospect.upsert', $targetType, $targetEntity->getId(), $sourceId, [
                    'deduplicated' => true,
                    'identityCreated' => $identityCreated,
                    'contactPolicy' => $policy,
                ]);
                $tx->commit();
                return $response;
            }

            $lead = $targetType === 'Lead' ? $targetEntity : null;
            if (!$lead) {
                $lead = $this->repo('Lead')->forUpdate()->where([
                    'fusanheSourceSystem' => self::SOURCE_SYSTEM,
                    'fusanheSourceId' => $sourceId,
                ])->findOne();
            }
            $createdLead = !$lead;
            if (!$lead) {
                $lead = $this->em->getNewEntity('Lead');
            }
            $this->writeLead($lead, $profile, $sourceId, $sourceUrl, $campaignKey, $policy, $agent->get('agentKey'), $createdLead);
            $this->kernel->save($lead);
            $identity->set([
                'leadId' => $lead->getId(),
                'linkStatus' => 'confirmed',
                'confirmedAt' => $identity->get('confirmedAt') ?: $now,
            ]);
            $this->kernel->save($identity);

            $response = $this->prospectResponse($identity, $lead, 'Lead', !$createdLead, $identityCreated, $policy);
            $this->audit($agent, 'muse.prospect.upsert', 'Lead', $lead->getId(), $sourceId, [
                'deduplicated' => !$createdLead,
                'identityCreated' => $identityCreated,
                'contactPolicy' => $policy,
            ]);
            $tx->commit();
            return $response;
        } catch (\Throwable $error) {
            $tx->rollback();
            throw $error;
        }
    }

    public function recordActivity(stdClass $input, Entity $agent): array
    {
        $this->assertCapability($agent);
        $sourceId = $this->requiredString($input, 'sourceId', 191);
        $sourceAccount = $this->optionalString($input, 'sourceAccount', 191) ?: 'default';
        $messageExternalId = $this->requiredString($input, 'messageExternalId', 191);
        $body = $this->requiredString($input, 'body', self::MAX_BODY);
        $direction = $this->optionalString($input, 'direction', 20) ?: 'outbound';
        if (!in_array($direction, self::DIRECTIONS, true)) {
            throw new BadRequest('direction must be inbound or outbound.');
        }
        $channelType = $this->optionalString($input, 'channelType', 30) ?: 'Email';
        if (!in_array($channelType, self::CHANNEL_TYPES, true)) {
            throw new BadRequest('Unsupported channelType.');
        }
        $deliveryStatus = $this->activityStatus($input->deliveryStatus ?? null, $direction);
        $sentAt = $this->timestamp($input->sentAt ?? null);
        $contactPolicy = $input->contactPolicy ?? null;

        $tx = $this->em->getTransactionManager();
        $tx->start();
        try {
            $identity = $this->repo('ExternalIdentity')->forUpdate()->where([
                'identityKey' => $this->identityKey($sourceAccount, $sourceId),
            ])->findOne();
            if (!$identity) {
                throw new NotFound('Muse prospect must be upserted before recording activity.');
            }
            $target = $this->linkedTarget($identity);
            $lead = $target['type'] === 'Lead' ? $target['entity'] : null;
            if ($direction === 'outbound' && $lead && (bool) $lead->get('fusanheDoNotContact')) {
                throw new Forbidden('Prospect is marked do-not-contact.');
            }
            if ($contactPolicy !== null) {
                $policy = $this->policy($contactPolicy);
                if ($lead) {
                    $this->applyPolicy($lead, $policy);
                }
                if (in_array($policy, ['optedOut', 'restricted'], true) && $direction === 'outbound') {
                    throw new Forbidden('Prospect contact policy blocks outbound activity.');
                }
            }
            $channelAccount = $this->optionalString($input, 'channelAccountId', 191) ?: 'default';
            $channel = $this->ensureChannel($channelType, $channelAccount);
            $conversationExternalId = $this->optionalString($input, 'conversationExternalId', 191)
                ?: $this->stableExternalId($sourceAccount . ':' . $sourceId . ':' . strtolower($channelType));
            $conversation = $this->repo('ExternalConversation')->forUpdate()->where([
                'channelId' => $channel->getId(),
                'externalId' => $conversationExternalId,
            ])->findOne();
            if (!$conversation) {
                $conversation = $this->em->getNewEntity('ExternalConversation');
                $conversation->set([
                    'name' => $this->optionalString($input, 'subject', 255) ?: 'Muse 触达 ' . $sourceId,
                    'subject' => $this->optionalString($input, 'subject', 255),
                    'channelId' => $channel->getId(),
                    'externalId' => $conversationExternalId,
                    'externalUserId' => $sourceId,
                    'identityId' => $identity->getId(),
                    'leadId' => $lead?->getId(),
                    'status' => $this->conversationStatus($direction, $deliveryStatus),
                    'controlMode' => 'aiAssist',
                    'needsManualMatch' => false,
                    // updateActivityState applies the first inbound unread
                    // increment after the message is persisted.
                    'unreadCount' => 0,
                    'language' => $this->optionalString($input, 'language', 20) ?: 'en',
                    'country' => (string) ($identity->get('country') ?? ''),
                    'lastMessageAt' => $sentAt,
                ]);
                $this->kernel->save($conversation);
            } else {
                $conversation->set(['identityId' => $identity->getId(), 'leadId' => $lead?->getId()]);
            }

            $existing = $this->repo('ExternalMessage')->forUpdate()->where([
                'conversationId' => $conversation->getId(),
                'externalId' => $messageExternalId,
            ])->findOne();
            if ($existing) {
                if ((string) $existing->get('body') !== $body || (string) $existing->get('direction') !== $direction) {
                    throw new Conflict('External message ID already contains different content.');
                }
                $existing->set('deliveryStatus', $deliveryStatus);
                $existing->set('sentAt', $sentAt);
                $this->kernel->save($existing);
                // A replay must not increment inbound unread counts again.
                // Status and delivery timestamps may still advance when a
                // sender replays the same external message ID.
                $this->updateActivityState($conversation, $lead, $direction, $deliveryStatus, $sentAt, $agent->get('agentKey'), $body, false);
                $this->kernel->save($conversation);
                $response = [
                    'conversationId' => $conversation->getId(),
                    'messageId' => $existing->getId(),
                    'prospectId' => $lead?->getId(),
                    'status' => $deliveryStatus,
                    'deduplicated' => true,
                ];
                $this->audit($agent, 'muse.activity.recorded', 'ExternalMessage', $existing->getId(), $sourceId, ['deduplicated' => true, 'direction' => $direction]);
                $tx->commit();
                return $response;
            }

            $hash = hash('sha256', implode('|', [$conversation->getId(), $messageExternalId, $direction, $body]));
            $message = $this->em->getNewEntity('ExternalMessage');
            $message->set([
                'name' => ($direction === 'inbound' ? 'IN ' : 'OUT ') . $messageExternalId,
                'conversationId' => $conversation->getId(),
                'externalId' => $messageExternalId,
                'direction' => $direction,
                'senderName' => $this->optionalString($input, 'senderName', 255) ?: ($direction === 'inbound' ? 'Customer' : 'Muse'),
                'senderExternalId' => $sourceId,
                'sentAt' => $sentAt,
                'body' => $body,
                'deliveryStatus' => $deliveryStatus,
                'contentHash' => $hash,
                'rawPayload' => ['source' => self::SOURCE_SYSTEM, 'externalId' => $messageExternalId],
            ]);
            $this->kernel->save($message);
            $this->updateActivityState($conversation, $lead, $direction, $deliveryStatus, $sentAt, $agent->get('agentKey'), $body);
            $this->kernel->save($conversation);
            $response = [
                'conversationId' => $conversation->getId(),
                'messageId' => $message->getId(),
                'prospectId' => $lead?->getId(),
                'status' => $deliveryStatus,
                'deduplicated' => false,
            ];
            $this->audit($agent, 'muse.activity.recorded', 'ExternalMessage', $message->getId(), $sourceId, ['deduplicated' => false, 'direction' => $direction]);
            $tx->commit();
            return $response;
        } catch (\Throwable $error) {
            $tx->rollback();
            throw $error;
        }
    }

    private function writeLead(Entity $lead, array $profile, string $sourceId, string $sourceUrl, string $campaignKey, string $policy, string $agentKey, bool $new): void
    {
        if ($new) {
            $display = $profile['displayName'] ?: ($profile['company'] ?: ($profile['email'] ?: 'Muse prospect ' . $sourceId));
            $parts = preg_split('/\s+/', $display, 2) ?: [$display];
            $lead->set([
                'name' => $display,
                'firstName' => $profile['firstName'] ?: (count($parts) > 1 ? $parts[0] : null),
                'lastName' => $profile['lastName'] ?: $parts[count($parts) - 1],
                'status' => 'New',
                'source' => 'Web Site',
                'accountName' => $profile['company'] ?: null,
                'emailAddress' => $profile['email'] ?: null,
                'phoneNumber' => $profile['phone'] ?: null,
                'addressCountry' => $profile['country'] ?: null,
                'website' => $profile['website'] ?: null,
                'description' => $profile['notes'] ?: ('来源：Muse；sourceId：' . $sourceId),
            ]);
        } else {
            foreach (['emailAddress' => 'email', 'phoneNumber' => 'phone', 'addressCountry' => 'country', 'website' => 'website', 'accountName' => 'company'] as $field => $key) {
                if ($profile[$key] !== '' && trim((string) $lead->get($field)) === '') {
                    $lead->set($field, $profile[$key]);
                }
            }
            if ($profile['notes'] !== '' && trim((string) $lead->get('description')) === '') {
                $lead->set('description', $profile['notes']);
            }
        }
        $currentSource = trim((string) ($lead->get('fusanheSourceSystem') ?: ''));
        $values = [
            'fusanheContactPolicy' => $this->mergedPolicy((string) ($lead->get('fusanheContactPolicy') ?: 'unknown'), $policy),
            'fusanheDoNotContact' => (bool) $lead->get('fusanheDoNotContact') || in_array($policy, ['optedOut', 'restricted'], true),
            'fusanheLastAgentKey' => $agentKey,
        ];
        // A manually linked Lead from another source owns its provenance. Muse
        // may attach the identity and update contact policy, but may not erase
        // that source attribution.
        if ($new || $currentSource === '' || $currentSource === self::SOURCE_SYSTEM) {
            $values += [
                'fusanheSourceSystem' => self::SOURCE_SYSTEM,
                'fusanheSourceId' => $sourceId,
                'fusanheSourceUrl' => $sourceUrl ?: $lead->get('fusanheSourceUrl'),
                'fusanheCampaignKey' => $campaignKey ?: $lead->get('fusanheCampaignKey'),
            ];
        }
        $lead->set($values);
    }

    private function updateActivityState(Entity $conversation, ?Entity $lead, string $direction, string $status, string $sentAt, string $agentKey, string $body, bool $countInbound = true): void
    {
        $preview = mb_substr((string) preg_replace('/\s+/', ' ', $body), 0, 220);
        $updates = [
            'lastMessageAt' => $sentAt,
            'lastMessagePreview' => $preview,
            'status' => $this->conversationStatus($direction, $status),
        ];
        if ($direction === 'inbound' && $countInbound) {
            $updates['lastInboundAt'] = $sentAt;
            $updates['unreadCount'] = ((int) $conversation->get('unreadCount')) + 1;
        } elseif ($direction === 'inbound') {
            $updates['lastInboundAt'] = $sentAt;
        } else {
            $updates['lastOutboundAt'] = $sentAt;
            $updates['unreadCount'] = 0;
        }
        $conversation->set($updates);
        if ($lead && $direction === 'outbound' && in_array($status, ['sent', 'delivered', 'mockSent'], true)) {
            $lead->set(['fusanheLastContactAt' => $sentAt, 'fusanheLastAgentKey' => $agentKey]);
            $this->kernel->save($lead);
        }
    }

    private function ensureChannel(string $type, string $accountHandle): Entity
    {
        $channel = $this->repo('ExternalChannel')->forUpdate()->where(['type' => $type, 'accountHandle' => $accountHandle])->findOne();
        if ($channel) {
            if (!(bool) $channel->get('enabled')) {
                throw new Conflict('Channel is disabled.');
            }
            return $channel;
        }
        $channel = $this->em->getNewEntity('ExternalChannel');
        $channel->set([
            'name' => $type . ' · ' . $accountHandle,
            'type' => $type,
            'accountHandle' => $accountHandle,
            'enabled' => true,
            'connectionStatus' => 'unknown',
        ]);
        $this->kernel->save($channel);
        return $channel;
    }

    /** @return array{type:string,entity:?Entity} */
    private function linkedTarget(Entity $identity): array
    {
        foreach (['Account' => 'accountId', 'Contact' => 'contactId', 'Lead' => 'leadId'] as $type => $field) {
            $id = trim((string) $identity->get($field));
            if ($id === '') {
                continue;
            }
            $entity = $this->em->getEntityById($type, $id);
            if ($entity) {
                return ['type' => $type, 'entity' => $entity];
            }
        }
        return ['type' => '', 'entity' => null];
    }

    private function leadProjection(Entity $lead): array
    {
        return [
            'prospectId' => $lead->getId(),
            'name' => (string) $lead->get('name'),
            'company' => (string) ($lead->get('accountName') ?: ''),
            'email' => (string) ($lead->get('emailAddress') ?: ''),
            'phone' => (string) ($lead->get('phoneNumber') ?: ''),
            'country' => (string) ($lead->get('addressCountry') ?: ''),
            'sourceSystem' => (string) ($lead->get('fusanheSourceSystem') ?: ''),
            'sourceId' => (string) ($lead->get('fusanheSourceId') ?: ''),
            'sourceUrl' => (string) ($lead->get('fusanheSourceUrl') ?: ''),
            'campaignKey' => (string) ($lead->get('fusanheCampaignKey') ?: ''),
            'contactPolicy' => (string) ($lead->get('fusanheContactPolicy') ?: 'unknown'),
            'doNotContact' => (bool) $lead->get('fusanheDoNotContact'),
        ];
    }

    private function prospectResponse(Entity $identity, Entity $target, string $targetType, bool $deduplicated, bool $identityCreated, string $policy): array
    {
        $projection = $targetType === 'Lead' ? $this->leadProjection($target) : [
            'prospectId' => null,
            'name' => (string) $target->get('name'),
            'company' => '',
            'email' => (string) ($target->get('emailAddress') ?: ''),
            'phone' => (string) ($target->get('phoneNumber') ?: ''),
            'country' => '',
            'sourceSystem' => self::SOURCE_SYSTEM,
            'sourceId' => (string) $identity->get('externalUserId'),
            'sourceUrl' => '',
            'campaignKey' => '',
            'contactPolicy' => $policy,
            'doNotContact' => false,
        ];
        return $projection + [
            'targetType' => $targetType,
            'targetId' => $target->getId(),
            'identityId' => $identity->getId(),
            'deduplicated' => $deduplicated,
            'identityCreated' => $identityCreated,
        ];
    }

    private function audit(Entity $agent, string $event, string $entityType, string $entityId, string $sourceId, array $details): void
    {
        $this->kernel->audit($event, 'agent', (string) $agent->get('agentKey'), $entityType, $entityId, 'success', ['sourceId' => $sourceId] + $details);
    }

    private function identityKey(string $account, string $sourceId): string
    {
        $raw = 'Other|Muse:' . $account . '|uid:' . $sourceId;
        return mb_strlen($raw) <= 191 ? $raw : 'Other|MuseHash:' . hash('sha256', $raw);
    }

    private function stableMuseAccountId(string $account): string
    {
        $value = 'Muse:' . $account;
        return mb_strlen($value) <= 191 ? $value : 'MuseHash:' . hash('sha256', $value);
    }

    private function stableExternalId(string $raw): string
    {
        $value = 'muse:' . $raw;
        return mb_strlen($value) <= 191 ? $value : 'muse:' . hash('sha256', $value);
    }

    private function profile(stdClass $input): array
    {
        return [
            'displayName' => $this->optionalString($input, 'displayName', 255),
            'firstName' => $this->optionalString($input, 'firstName', 100),
            'lastName' => $this->optionalString($input, 'lastName', 100),
            'company' => $this->optionalString($input, 'company', 255),
            'email' => $this->optionalString($input, 'email', 255),
            'phone' => $this->optionalString($input, 'phone', 100),
            'country' => $this->optionalString($input, 'country', 100),
            'website' => $this->optionalString($input, 'website', 2000),
            'notes' => $this->optionalString($input, 'notes', self::MAX_NOTE),
        ];
    }

    private function applyPolicy(Entity $lead, string $policy): void
    {
        if ($policy === 'unknown') {
            return;
        }
        $lead->set([
            'fusanheContactPolicy' => $this->mergedPolicy((string) ($lead->get('fusanheContactPolicy') ?: 'unknown'), $policy),
            'fusanheDoNotContact' => (bool) $lead->get('fusanheDoNotContact') || in_array($policy, ['optedOut', 'restricted'], true),
        ]);
        $this->kernel->save($lead);
    }

    private function mergedPolicy(string $current, string $incoming): string
    {
        if (in_array($current, ['optedOut', 'restricted'], true)) {
            return $current;
        }
        if (in_array($incoming, ['optedOut', 'restricted'], true)) {
            return $incoming;
        }
        return $incoming !== 'unknown' ? $incoming : ($current ?: 'unknown');
    }

    private function policy(mixed $value): string
    {
        $policy = trim((string) $value);
        if (!in_array($policy, self::POLICIES, true)) {
            throw new BadRequest('contactPolicy is invalid.');
        }
        return $policy;
    }

    private function activityStatus(mixed $value, string $direction): string
    {
        $status = trim((string) ($value ?? ($direction === 'inbound' ? 'received' : 'queued')));
        if (!in_array($status, self::DELIVERY_STATUSES, true)) {
            throw new BadRequest('deliveryStatus is invalid.');
        }
        if ($direction === 'inbound' && $status !== 'received') {
            throw new BadRequest('Inbound activity must use received status.');
        }
        if ($direction === 'outbound' && $status === 'received') {
            throw new BadRequest('Outbound activity cannot use received status.');
        }
        return $status;
    }

    private function conversationStatus(string $direction, string $deliveryStatus): string
    {
        if ($direction === 'inbound') {
            return 'pending';
        }
        return in_array($deliveryStatus, ['sent', 'delivered', 'mockSent'], true) ? 'sent' : 'readyToSend';
    }

    private function timestamp(mixed $value): string
    {
        $raw = trim((string) ($value ?? ''));
        if ($raw === '') {
            return $this->kernel->now();
        }
        try {
            $date = new DateTimeImmutable($raw, new DateTimeZone('Asia/Shanghai'));
            return $date->setTimezone(new DateTimeZone('UTC'))->format('Y-m-d H:i:s');
        } catch (\Throwable) {
            throw new BadRequest('sentAt must be a valid timestamp.');
        }
    }

    private function requiredString(stdClass $input, string $field, int $max): string
    {
        $value = $this->optionalString($input, $field, $max);
        if ($value === '') {
            throw new BadRequest($field . ' is required.');
        }
        return $value;
    }

    private function optionalString(stdClass $input, string $field, int $max): string
    {
        $value = trim((string) ($input->{$field} ?? ''));
        if (mb_strlen($value) > $max) {
            throw new BadRequest($field . ' exceeds maximum length.');
        }
        return $value;
    }

    private function repo(string $type)
    {
        return $this->em->getRDBRepository($type);
    }
}
