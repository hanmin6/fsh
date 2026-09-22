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
 * Cross-channel identity mapping for unregistered customers.
 *
 * Identity uniqueness covers the channel type, the channel account instance
 * and the external user id; anonymous visitors (no external user id, no
 * contact data) are kept per conversation so they are never merged together.
 * Linking an identity to a CRM customer is an explicit, audited, permission
 * checked action - weak evidence never links automatically and unknown
 * inquiries no longer auto-create Leads.
 */
final class IdentityService
{
    private const TARGET_MAP = [
        'Account' => 'accountId',
        'Contact' => 'contactId',
        'Lead' => 'leadId',
    ];

    public function __construct(
        private EntityManager $em,
        private Acl $acl,
        private User $user,
        private ServiceKernel $kernel,
    ) {}

    public function buildIdentityKey(
        string $channelType,
        string $channelAccountId,
        string $externalUserId,
        string $email,
        string $phone,
        string $conversationExternalId,
    ): string {
        $channelType = trim($channelType) !== '' ? trim($channelType) : 'Other';
        $channelAccountId = trim($channelAccountId) !== '' ? trim($channelAccountId) : 'default';
        if (trim($externalUserId) !== '') {
            return implode('|', [$channelType, $channelAccountId, 'uid:' . trim($externalUserId)]);
        }
        if (trim($email) !== '') {
            return implode('|', [$channelType, $channelAccountId, 'email:' . mb_strtolower(trim($email))]);
        }
        if (trim($phone) !== '') {
            $phone = preg_replace('/[\s\-()]/', '', trim($phone)) ?? trim($phone);
            return implode('|', [$channelType, $channelAccountId, 'phone:' . $phone]);
        }
        // Anonymous visitor: scoped to this conversation only, never merged.
        return implode('|', [$channelType, $channelAccountId, 'anon:' . $conversationExternalId]);
    }

    /**
     * Finds or creates the identity for an inbound conversation and updates
     * its contact profile. Returns [identity, created].
     */
    public function resolveIdentity(
        string $channelType,
        string $channelAccountId,
        string $externalUserId,
        string $email,
        string $phone,
        string $conversationExternalId,
        array $profile = [],
    ): array {
        $key = $this->buildIdentityKey($channelType, $channelAccountId, $externalUserId, $email, $phone, $conversationExternalId);
        $identity = $this->repo()->where(['identityKey' => $key])->findOne();
        $created = false;
        $now = gmdate('Y-m-d H:i:s');
        if (!$identity) {
            $identity = $this->em->getNewEntity('ExternalIdentity');
            $values = [
                'name' => $profile['displayName'] ?? ('身份 ' . substr($key, 0, 40)),
                'identityKey' => $key,
                'channelType' => $channelType !== '' ? $channelType : 'Other',
                'channelAccountId' => $channelAccountId !== '' ? $channelAccountId : 'default',
                'externalUserId' => trim($externalUserId),
                'linkStatus' => 'unlinked',
                'firstSeenAt' => $now,
                'lastSeenAt' => $now,
            ];
            foreach (['displayName', 'emailAddress', 'phoneNumber', 'country'] as $field) {
                if (!empty($profile[$field])) {
                    $values[$field] = $profile[$field];
                }
            }
            $identity->set($values);
            $created = true;
        } else {
            $updates = ['lastSeenAt' => $now];
            foreach (['displayName', 'emailAddress', 'phoneNumber', 'country'] as $field) {
                if (!empty($profile[$field]) && !$identity->get($field)) {
                    $updates[$field] = $profile[$field];
                }
            }
            if (!$identity->get('externalUserId') && trim($externalUserId) !== '') {
                $updates['externalUserId'] = trim($externalUserId);
            }
            if (
                !$identity->get('name') ||
                $identity->get('name') === $identity->get('identityKey')
            ) {
                $updates['name'] = $profile['displayName'] ?? $identity->get('name');
            }
            $identity->set($updates);
        }
        $this->kernel->save($identity);
        return [$identity, $created];
    }

    /**
     * Refreshes only missing integration profile values for an already-linked
     * conversation identity.  The identity key is immutable: a later stable
     * platform id is recorded when absent but never repartitions old history.
     */
    public function refreshIntegrationProfile(Entity $identity, string $externalUserId, array $profile): Entity
    {
        $updates = ['lastSeenAt' => gmdate('Y-m-d H:i:s')];
        foreach (['displayName', 'emailAddress', 'phoneNumber', 'country'] as $field) {
            if (!empty($profile[$field]) && !$identity->get($field)) {
                $updates[$field] = $profile[$field];
            }
        }
        if (!$identity->get('externalUserId') && trim($externalUserId) !== '') {
            $updates['externalUserId'] = trim($externalUserId);
        }
        $identity->set($updates);
        $this->kernel->save($identity);
        return $identity;
    }

    /**
     * System-only matching used by the Alibaba importer.  It deliberately
     * accepts only a unique, exact contact method: names and countries are
     * useful profile data but are never evidence for merging customers.
     */
    public function resolveAutomaticCustomer(Entity $identity, string $conversationExternalId): array
    {
        foreach (self::TARGET_MAP as $type => $field) {
            $id = (string) $identity->get($field);
            if ($identity->get('linkStatus') === 'confirmed' && $id !== '' && $this->em->getEntityById($type, $id)) {
                return [
                    'targetType' => $type,
                    'targetId' => $id,
                    'createdLead' => false,
                    'matchMethod' => 'existingConfirmed',
                ];
            }
        }

        $email = trim((string) $identity->get('emailAddress'));
        $rawPhone = trim((string) $identity->get('phoneNumber'));
        $phone = $this->normalisePhone($rawPhone);
        $emailCandidates = $email === '' ? [] : $this->automaticCandidates('emailAddress', $email);
        $phoneCandidates = $phone === '' ? [] : $this->phoneCandidates($rawPhone, $phone);
        $candidates = [];
        foreach (array_merge($emailCandidates, $phoneCandidates) as $candidate) {
            $candidates[$candidate['type'] . ':' . $candidate['entity']->getId()] = $candidate;
        }

        if (count($candidates) === 1) {
            $candidate = array_values($candidates)[0];
            $type = $candidate['type'];
            $field = self::TARGET_MAP[$type];
            $emailMatches = array_filter($emailCandidates, fn(array $item) => $item['type'] === $type && $item['entity']->getId() === $candidate['entity']->getId());
            $phoneMatches = array_filter($phoneCandidates, fn(array $item) => $item['type'] === $type && $item['entity']->getId() === $candidate['entity']->getId());
            $identity->set([
                $field => $candidate['entity']->getId(),
                'linkStatus' => 'confirmed',
                'confirmedAt' => gmdate('Y-m-d H:i:s'),
            ]);
            $this->kernel->save($identity);
            return [
                'targetType' => $type,
                'targetId' => $candidate['entity']->getId(),
                'createdLead' => false,
                'matchMethod' => $emailMatches && $phoneMatches ? 'uniqueEmailPhone' : ($emailMatches ? 'uniqueEmail' : 'uniquePhone'),
            ];
        }

        $lead = $this->ensureLeadForIdentity($identity, $conversationExternalId);
        return [
            'targetType' => 'Lead',
            'targetId' => $lead->getId(),
            'createdLead' => true,
            'matchMethod' => count($candidates) === 0 ? 'newLead' : 'ambiguousNewLead',
        ];
    }

    /** Creates the narrowest CRM record possible for an unambiguous inquiry. */
    public function ensureLeadForIdentity(Entity $identity, string $conversationExternalId): Entity
    {
        $leadId = (string) $identity->get('leadId');
        if ($leadId !== '') {
            $lead = $this->em->getEntityById('Lead', $leadId);
            if ($lead) {
                return $lead;
            }
        }
        $displayName = trim((string) $identity->get('displayName'));
        if ($displayName === '') {
            throw new Conflict('Identity has no display name to create an Alibaba Lead.');
        }
        $nameParts = preg_split('/\\s+/', $displayName, 2) ?: [$displayName];
        $lead = $this->em->getNewEntity('Lead');
        $lead->set([
            'name' => $displayName,
            'lastName' => $nameParts[count($nameParts) - 1],
            'firstName' => count($nameParts) > 1 ? $nameParts[0] : null,
            'status' => 'New',
            'source' => 'Web Site',
            'emailAddress' => (string) $identity->get('emailAddress'),
            'phoneNumber' => (string) $identity->get('phoneNumber'),
            'addressCountry' => (string) $identity->get('country'),
            'description' => '来源：Alibaba；询价单；身份key：' . $identity->get('identityKey') . '；询盘：' . $conversationExternalId,
        ]);
        $this->kernel->save($lead);
        $identity->set([
            'leadId' => $lead->getId(),
            'linkStatus' => 'confirmed',
            'confirmedAt' => gmdate('Y-m-d H:i:s'),
        ]);
        $this->kernel->save($identity);
        return $lead;
    }

    /**
     * Strong-evidence candidates (exact email or phone match) for linking an
     * identity to an existing customer. Candidates are filtered by the
     * caller's read permission, so out-of-scope customers never leak.
     */
    public function findCandidates(string $identityId, string $conversationId): array
    {
        $identity = $this->getIdentityForConversation($identityId, $conversationId);
        $email = trim((string) $identity->get('emailAddress'));
        $phone = trim((string) $identity->get('phoneNumber'));
        if ($email === '' && $phone === '') {
            return [];
        }
        $candidates = [];
        foreach (['Account', 'Contact', 'Lead'] as $type) {
            $where = [];
            if ($email !== '') {
                $where[] = ['emailAddress' => $email];
            }
            if ($phone !== '') {
                $where[] = ['phoneNumber' => $phone];
            }
            foreach ($this->repo($type)->where($where)->limit(0, 10)->find() as $entity) {
                if (!$this->acl->checkEntityRead($entity)) {
                    continue;
                }
                $candidates[$type . ':' . $entity->getId()] = [
                    'id' => $entity->getId(),
                    'type' => $type,
                    'name' => (string) $entity->get('name'),
                    'emailAddress' => (string) $entity->get('emailAddress'),
                    'phoneNumber' => (string) $entity->get('phoneNumber'),
                ];
            }
        }
        return array_values(array_slice($candidates, 0, 10));
    }

    /**
     * Explicitly links an identity to an existing Account/Contact/Lead and
     * propagates the link to the identity's conversations that are still
     * unlinked. Records the operator, the source and the before/after links.
     */
    public function link(string $identityId, string $conversationId, string $targetType, string $targetId): array
    {
        $identity = $this->getIdentityForConversation($identityId, $conversationId, edit: true);
        if (!isset(self::TARGET_MAP[$targetType])) {
            throw new BadRequest('targetType must be Account, Contact or Lead.');
        }
        $target = $this->em->getEntityById($targetType, $targetId);
        if (!$target) {
            throw new NotFound($targetType . ' not found.');
        }
        if (!$this->acl->checkEntityRead($target)) {
            throw new Forbidden('Not allowed to link this customer.');
        }
        if (!$this->acl->checkScope('ExternalIdentity', 'edit')) {
            throw new Forbidden('Not allowed to confirm identities.');
        }
        $field = self::TARGET_MAP[$targetType];
        $previous = [
            'accountId' => $identity->get('accountId'),
            'contactId' => $identity->get('contactId'),
            'leadId' => $identity->get('leadId'),
            'linkStatus' => $identity->get('linkStatus'),
        ];
        $identity->set([
            $field => $target->getId(),
            'linkStatus' => 'confirmed',
            'confirmedById' => $this->user->getId(),
            'confirmedAt' => gmdate('Y-m-d H:i:s'),
        ]);
        $this->kernel->save($identity);
        $propagated = $this->propagateToConversations($identity, $field, $target->getId());

        $this->kernel->audit(
            'identity.linked',
            'user',
            $this->user->getId(),
            'ExternalIdentity',
            $identity->getId(),
            'success',
            [
                'targetType' => $targetType,
                'targetId' => $target->getId(),
                'conversationId' => $conversationId,
                'before' => $previous,
                'after' => [$field => $target->getId(), 'linkStatus' => 'confirmed'],
                'conversationsLinked' => $propagated,
            ],
        );
        return [
            'identityId' => $identity->getId(),
            'linkStatus' => 'confirmed',
            'targetType' => $targetType,
            'targetId' => $target->getId(),
            'conversationsLinked' => $propagated,
        ];
    }

    /**
     * Explicit customer creation from an identity (no silent duplicates):
     * the caller must actively choose this action and the target type.
     */
    public function createCustomer(string $identityId, string $conversationId, string $targetType): array
    {
        $identity = $this->getIdentityForConversation($identityId, $conversationId, edit: true);
        if (!isset(self::TARGET_MAP[$targetType])) {
            throw new BadRequest('targetType must be Account, Contact or Lead.');
        }
        if (!$this->acl->checkScope($targetType, 'create')) {
            throw new Forbidden('Not allowed to create ' . $targetType . '.');
        }
        if (!$this->acl->checkScope('ExternalIdentity', 'edit')) {
            throw new Forbidden('Not allowed to confirm identities.');
        }
        $displayName = trim((string) ($identity->get('displayName') ?: $identity->get('name')));
        if ($displayName === '') {
            throw new Conflict('Identity has no display name to build a customer record.');
        }
        $values = [
            'name' => $displayName,
            'emailAddress' => (string) $identity->get('emailAddress'),
            'phoneNumber' => (string) $identity->get('phoneNumber'),
            'assignedUserId' => $this->user->getId(),
        ];
        if ($targetType === 'Lead') {
            $values['lastName'] = $displayName;
            $values['status'] = 'New';
            $values['source'] = 'Web Site';
            $values['addressCountry'] = (string) $identity->get('country');
            $values['description'] = '由 AI 客服会话人工建档创建，来源身份：' . $identity->get('identityKey');
        } elseif ($targetType === 'Contact') {
            $values['lastName'] = $displayName;
        }
        $target = $this->em->getNewEntity($targetType);
        $target->set($values);
        $this->kernel->save($target);

        $field = self::TARGET_MAP[$targetType];
        $identity->set([
            $field => $target->getId(),
            'linkStatus' => 'confirmed',
            'confirmedById' => $this->user->getId(),
            'confirmedAt' => gmdate('Y-m-d H:i:s'),
        ]);
        $this->kernel->save($identity);
        $propagated = $this->propagateToConversations($identity, $field, $target->getId());

        $this->kernel->audit(
            'identity.customerCreated',
            'user',
            $this->user->getId(),
            $targetType,
            $target->getId(),
            'success',
            [
                'identityId' => $identity->getId(),
                'conversationId' => $conversationId,
                'conversationsLinked' => $propagated,
            ],
        );
        return [
            'identityId' => $identity->getId(),
            'linkStatus' => 'confirmed',
            'targetType' => $targetType,
            'targetId' => $target->getId(),
            'conversationsLinked' => $propagated,
        ];
    }

    /**
     * The identity is only manageable from a conversation the user can work
     * with: read is required for viewing candidates, edit for confirming.
     */
    private function getIdentityForConversation(string $identityId, string $conversationId, bool $edit = false): Entity
    {
        $identity = $this->em->getEntityById('ExternalIdentity', $identityId);
        if (!$identity) {
            throw new NotFound('ExternalIdentity not found.');
        }
        $conversation = $this->em->getEntityById('ExternalConversation', $conversationId);
        if (!$conversation) {
            throw new NotFound('ExternalConversation not found.');
        }
        if ((string) $conversation->get('identityId') !== $identity->getId()) {
            throw new Conflict('Conversation does not belong to this identity.');
        }
        if ($edit) {
            if (!$this->acl->checkEntityEdit($conversation)) {
                throw new Forbidden('Not allowed to operate on this conversation.');
            }
        } elseif (!$this->acl->checkEntityRead($conversation)) {
            throw new Forbidden('Not allowed to read this conversation.');
        }
        return $identity;
    }

    private function propagateToConversations(Entity $identity, string $field, string $targetId): int
    {
        $count = 0;
        foreach ($this->repo('ExternalConversation')->where(['identityId' => $identity->getId()])->find() as $conversation) {
            if ($conversation->get($field)) {
                continue;
            }
            $conversation->set([$field => $targetId, 'needsManualMatch' => false]);
            $this->kernel->save($conversation);
            $count++;
        }
        return $count;
    }

    private function repo(string $type = 'ExternalIdentity')
    {
        return $this->em->getRDBRepository($type);
    }

    private function automaticCandidates(string $field, string $value): array
    {
        $candidates = [];
        foreach (['Account', 'Contact', 'Lead'] as $type) {
            foreach ($this->repo($type)->where([$field => $value])->find() as $entity) {
                $candidates[] = ['type' => $type, 'entity' => $entity];
            }
        }
        return $candidates;
    }

    private function phoneCandidates(string $rawPhone, string $normalisedPhone): array
    {
        $candidates = [];
        foreach (['Account', 'Contact', 'Lead'] as $type) {
            foreach (array_unique([$rawPhone, $normalisedPhone]) as $queryPhone) {
                foreach ($this->repo($type)->where(['phoneNumber' => $queryPhone])->find() as $entity) {
                    if ($this->normalisePhone((string) $entity->get('phoneNumber')) !== $normalisedPhone) {
                        continue;
                    }
                    $candidates[$type . ':' . $entity->getId()] = ['type' => $type, 'entity' => $entity];
                }
            }
        }
        return array_values($candidates);
    }

    private function normalisePhone(string $phone): string
    {
        return preg_replace('/[^0-9+]/', '', trim($phone)) ?? trim($phone);
    }
}
