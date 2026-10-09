<?php
namespace Espo\Custom\Tools\Fusanhe;

use Espo\Core\Exceptions\BadRequest;
use Espo\Core\Exceptions\Conflict;
use Espo\Core\Exceptions\Forbidden;
use Espo\Core\Exceptions\NotFound;
use Espo\Entities\User;
use Espo\ORM\Entity;
use Espo\ORM\EntityManager;

/** CRM-only evidence and research boundary. It never sends or creates outbound tasks. */
final class OutreachEvidenceService
{
    public function __construct(
        private EntityManager $em,
        private ServiceKernel $kernel,
        private MediaStorage $storage,
        private TextGateway $gateway,
    ) {}

    public function record(object $input, User $user): array
    {
        $idempotencyKey = OutreachEvidencePolicy::idempotency($input->idempotencyKey ?? null);
        $targetType = OutreachEvidencePolicy::targetType($input->targetType ?? null);
        $targetId = OutreachEvidencePolicy::targetId($input->targetId ?? null);
        $target = $this->em->getEntityById($targetType, $targetId);
        if (!$target) throw new NotFound('Target customer not found.');
        $channel = OutreachEvidencePolicy::channel($input->channelType ?? null);
        $status = OutreachEvidencePolicy::status($input->sendStatus ?? 'uncertain');
        $body = OutreachEvidencePolicy::message($input->messageBody ?? null);
        $screenshot = OutreachEvidencePolicy::screenshot($input->screenshotDataUrl ?? null);
        $profileUrl = OutreachEvidencePolicy::url($input->profileUrl ?? '');
        $externalId = $this->boundedOptional($input->externalMessageId ?? null, 191);
        $accountId = $this->boundedOptional($input->channelAccountId ?? null, 191);
        $conversationId = $this->boundedOptional($input->conversationId ?? null, 24);
        $messageId = $this->boundedOptional($input->messageId ?? null, 24);
        $sentAt = OutreachEvidencePolicy::sentAt($input->sentAt ?? null);
        $snapshot = OutreachEvidencePolicy::customerSnapshot($input->customerSnapshot ?? null);
        if ($snapshot === []) $snapshot = $this->targetSnapshot($target, $profileUrl);
        $messageKey = $externalId !== '' ? hash('sha256', json_encode([$channel, $accountId, $targetType, $targetId, $externalId])) : null;
        $requestHash = hash('sha256', json_encode([
            $targetType, $targetId, $channel, $accountId, $externalId, $profileUrl, $body, $status, $sentAt,
            $snapshot, $conversationId, $messageId, $screenshot['sha256'],
        ], JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES | JSON_THROW_ON_ERROR));

        return $this->storage->locked(function () use ($idempotencyKey, $targetType, $targetId, $target, $channel, $status, $body, $screenshot, $profileUrl, $externalId, $accountId, $conversationId, $messageId, $sentAt, $snapshot, $requestHash, $messageKey, $user) {
            $existing = $this->repo('OutreachEvidence')->where(['idempotencyKey' => $idempotencyKey])->findOne();
            if ($existing) {
                $this->assertOwner($existing, $user);
                if ((string) $existing->get('requestHash') !== $requestHash) throw new Conflict('Idempotency key was already used for different evidence.');
                return $this->view($existing);
            }
            if ($externalId !== '') {
                $sameMessage = $this->repo('OutreachEvidence')->where(['messageKey' => $messageKey])->findOne();
                if ($sameMessage) {
                    $this->assertOwner($sameMessage, $user);
                    if ((string) $sameMessage->get('requestHash') !== $requestHash) throw new Conflict('External message ID already contains different evidence.');
                    return $this->view($sameMessage);
                }
            }
            $fileKey = $this->storage->put($screenshot['bytes']);
            $evidence = $this->em->getNewEntity('OutreachEvidence');
            $values = [
                'name' => mb_substr($channel . ' 触达 · ' . ($snapshot['company'] ?? $snapshot['name'] ?? $target->get('name') ?? $targetId), 0, 255),
                'idempotencyKey' => $idempotencyKey,
                'requestHash' => $requestHash,
                'messageKey' => $messageKey,
                'externalMessageId' => $externalId ?: null,
                'channelType' => $channel,
                'channelAccountId' => $accountId ?: null,
                'conversationId' => $conversationId ?: null,
                'messageId' => $messageId ?: null,
                'profileUrl' => $profileUrl ?: null,
                'messageBody' => $body,
                'sendStatus' => $status,
                'sentAt' => $sentAt,
                'customerSnapshot' => $snapshot,
                'screenshotFileKey' => $fileKey,
                'screenshotMime' => $screenshot['mime'],
                'screenshotSize' => $screenshot['size'],
                'screenshotSha256' => $screenshot['sha256'],
                'screenshotWidth' => $screenshot['width'],
                'screenshotHeight' => $screenshot['height'],
                'researchStatus' => 'pending',
                'researchAttempts' => 0,
                'researchNextAt' => gmdate('Y-m-d H:i:s'),
                'assignedUserId' => $user->getId(),
                lcfirst($targetType) . 'Id' => $targetId,
            ];
            $evidence->set($values);
            $tx = $this->em->getTransactionManager();
            $tx->start();
            try {
                $this->kernel->save($evidence);
                $this->kernel->audit('outreach.evidence.recorded', 'user', $user->getId(), 'OutreachEvidence', $evidence->getId(), 'success', [
                    'channelType' => $channel, 'sendStatus' => $status, 'targetType' => $targetType, 'targetId' => $targetId,
                    'screenshotSha256' => $screenshot['sha256'],
                ]);
                $tx->commit();
            } catch (\Throwable $error) {
                $tx->rollback();
                $this->storage->remove($fileKey);
                throw $error;
            }
            return $this->view($evidence);
        });
    }

    public function view(Entity $evidence): array
    {
        return [
            'id' => $evidence->getId(),
            'name' => $evidence->get('name'),
            'idempotencyKey' => $evidence->get('idempotencyKey'),
            'externalMessageId' => $evidence->get('externalMessageId'),
            'channelType' => $evidence->get('channelType'),
            'channelAccountId' => $evidence->get('channelAccountId'),
            'profileUrl' => $evidence->get('profileUrl'),
            'messageBody' => $evidence->get('messageBody'),
            'sendStatus' => $evidence->get('sendStatus'),
            'sentAt' => $evidence->get('sentAt'),
            'customerSnapshot' => $evidence->get('customerSnapshot'),
            'screenshot' => [
                'available' => (string) $evidence->get('screenshotFileKey') !== '',
                'mime' => $evidence->get('screenshotMime'),
                'size' => $evidence->get('screenshotSize'),
                'sha256' => $evidence->get('screenshotSha256'),
                'width' => $evidence->get('screenshotWidth'),
                'height' => $evidence->get('screenshotHeight'),
            ],
            'researchStatus' => $evidence->get('researchStatus'),
            'researchAttempts' => $evidence->get('researchAttempts'),
            'researchNextAt' => $evidence->get('researchNextAt'),
            'researchAt' => $evidence->get('researchAt'),
            'researchModel' => $evidence->get('researchModel'),
            'researchVersion' => $evidence->get('researchVersion'),
            'researchError' => $evidence->get('researchError'),
            'researchData' => $evidence->get('researchData'),
            'leadId' => $evidence->get('leadId'),
            'accountId' => $evidence->get('accountId'),
            'contactId' => $evidence->get('contactId'),
            'conversationId' => $evidence->get('conversationId'),
            'messageId' => $evidence->get('messageId'),
            'createdAt' => $evidence->get('createdAt'),
        ];
    }

    /** ACL-scoped, bounded projection for the customer workbench list. */
    public function list(string $targetType, string $targetId, User $user, int $offset = 0, int $limit = 30): array
    {
        $targetType = OutreachEvidencePolicy::targetType($targetType);
        $targetId = OutreachEvidencePolicy::targetId($targetId);
        $offset = max(0, $offset);
        $limit = min(50, max(1, $limit));
        $where = [lcfirst($targetType) . 'Id' => $targetId];
        if (!$user->isAdmin()) $where['assignedUserId'] = $user->getId();
        $repo = $this->repo('OutreachEvidence');
        $total = $repo->where($where)->count();
        $list = [];
        foreach ($repo->where($where)->order('sentAt', 'DESC')->order('id', 'DESC')->limit($offset, $limit)->find() as $evidence) {
            $list[] = [
                'id' => $evidence->getId(),
                'name' => $evidence->get('name'),
                'channelType' => $evidence->get('channelType'),
                'sendStatus' => $evidence->get('sendStatus'),
                'sentAt' => $evidence->get('sentAt'),
                'profileUrl' => $evidence->get('profileUrl'),
                'screenshot' => ['available' => (string) $evidence->get('screenshotFileKey') !== ''],
                'researchStatus' => $evidence->get('researchStatus'),
                'researchAttempts' => $evidence->get('researchAttempts'),
                'leadId' => $evidence->get('leadId'),
                'accountId' => $evidence->get('accountId'),
                'contactId' => $evidence->get('contactId'),
            ];
        }
        return ['list' => $list, 'total' => $total, 'offset' => $offset, 'limit' => $limit];
    }

    public function screenshot(Entity $evidence): array
    {
        $key = (string) $evidence->get('screenshotFileKey');
        if ($key === '') throw new NotFound('Screenshot is not available.');
        $mime = (string) $evidence->get('screenshotMime');
        if (!in_array($mime, ['image/png', 'image/jpeg', 'image/webp'], true)) throw new NotFound('Screenshot is not available.');
        $bytes = $this->storage->get($key);
        if (!hash_equals((string) $evidence->get('screenshotSha256'), hash('sha256', $bytes))) throw new Conflict('Screenshot integrity check failed.');
        return ['id' => $evidence->getId(), 'mime' => $mime, 'sha256' => $evidence->get('screenshotSha256'), 'dataUrl' => 'data:' . $mime . ';base64,' . base64_encode($bytes)];
    }

    public function research(Entity $evidence, User $user): array
    {
        $lockPath = 'data/outreach-research-' . hash('sha256', $evidence->getId()) . '.lock';
        $lock = fopen($lockPath, 'c');
        if (!$lock || !flock($lock, LOCK_EX | LOCK_NB)) { if ($lock) fclose($lock); return ['status' => 'busy', 'id' => $evidence->getId()]; }
        $research = null;
        try {
            $fresh = $this->repo('OutreachEvidence')->where(['id' => $evidence->getId()])->findOne();
            if (!$fresh) throw new NotFound('Outreach evidence not found.');
            if ($fresh->get('researchStatus') === 'completed' || (int) $fresh->get('researchAttempts') >= 3) return $this->view($fresh);
            $attempts = (int) $fresh->get('researchAttempts') + 1;
            $target = $this->targetFromEvidence($fresh);
            $snapshot = OutreachEvidencePolicy::customerSnapshot($fresh->get('customerSnapshot'));
            $profileUrl = (string) ($fresh->get('profileUrl') ?? '');
            $safe = OutreachEvidencePolicy::safeResearchInput($snapshot, $profileUrl, (string) $fresh->get('messageBody'));
            $input = [
                'customer' => $safe['customer'],
                'messages' => [],
                'totalMessages' => 0, 'includedMessages' => 0, 'historyTruncated' => false,
                'profileUrl' => $safe['profileUrl'], 'messageContext' => $safe['messageContext'], 'asOfUtc' => gmdate('c'),
            ];
            $now = gmdate('Y-m-d H:i:s');
            $fresh->set(['researchStatus' => 'running', 'researchAttempts' => $attempts, 'researchNextAt' => gmdate('Y-m-d H:i:s', time() + 900), 'researchError' => null]);
            $this->kernel->save($fresh);
            $research = $this->repo('ProspectResearch')->where(['evidenceId' => $fresh->getId()])->findOne();
            if (!$research) {
                $research = $this->em->getNewEntity('ProspectResearch');
                $research->set(['name' => '触达背调 · ' . $fresh->getId(), 'targetType' => $target['type'], 'targetId' => $target['id'], 'evidenceId' => $fresh->getId(), 'assignedUserId' => $user->getId()]);
            }
            $research->set(['status' => 'running', 'inputSnapshot' => $input, 'startedAt' => $now, 'nextAt' => null, 'errorCode' => null]);
            $this->kernel->save($research);
            try {
                $result = $this->gateway->research($input);
                $data = $result['data'];
                $sources = $data['sources'] ?? [];
                $report = trim(implode("\n", array_filter([
                    '公司匹配：' . (($data['company']['matchStatus'] ?? 'unverified') === 'confirmed' ? '已确认' : (($data['company']['matchStatus'] ?? '') === 'possible' ? '候选' : '未确认')),
                    '判断：' . (string) ($data['reason'] ?? ''),
                    '下一步：' . (string) ($data['nextAction'] ?? ''),
                    '待补充：' . implode('；', array_slice((array) ($data['missingInformation'] ?? []), 0, 5)),
                ])));
                $version = hash('sha256', json_encode([$input, OutreachEvidencePolicy::VERSION, $this->gateway->fingerprint()], JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES));
                $completed = gmdate('Y-m-d H:i:s');
                $fresh->set(['researchStatus' => 'completed', 'researchAt' => $completed, 'researchModel' => $result['model'], 'researchVersion' => $version, 'researchData' => $data, 'researchError' => null, 'researchNextAt' => null]);
                $this->kernel->save($fresh);
                $research->set(['status' => 'completed', 'report' => mb_substr($report, 0, 12000), 'data' => $data, 'sources' => $sources, 'queries' => $result['queries'] ?? [], 'model' => $result['model'], 'promptVersion' => $data['promptVersion'] ?? CustomerRatingPolicy::VERSION, 'completedAt' => $completed, 'nextAt' => null, 'errorCode' => null]);
                $this->kernel->save($research);
                $this->kernel->audit('outreach.research.completed', 'user', $user->getId(), 'OutreachEvidence', $fresh->getId(), 'success', ['sourceCount' => count($sources), 'model' => $result['model']]);
                return $this->view($fresh);
            } catch (\Throwable $error) {
                $code = in_array($error->getMessage(), ['rating_search_model_unavailable','rating_rate_limited','rating_web_search_not_executed','rating_invalid_result','rating_incomplete_response','text_rate_limited','text_transport_failed'], true) ? $error->getMessage() : 'outreach_research_failed';
                $next = gmdate('Y-m-d H:i:s', time() + 600);
                $fresh->set(['researchStatus' => 'failed', 'researchError' => $code, 'researchNextAt' => $attempts < 3 ? $next : null]);
                $this->kernel->save($fresh);
                $research->set(['status' => 'failed', 'errorCode' => $code, 'nextAt' => $attempts < 3 ? $next : null]);
                $this->kernel->save($research);
                $this->kernel->audit('outreach.research.failed', 'user', $user->getId(), 'OutreachEvidence', $fresh->getId(), 'failure', ['errorCode' => $code]);
                return $this->view($fresh);
            }
        } finally { flock($lock, LOCK_UN); fclose($lock); }
    }

    private function targetSnapshot(Entity $target, string $profileUrl): array
    {
        $values = [];
        foreach (['name', 'firstName', 'lastName', 'accountName', 'website', 'addressCountry', 'billingAddressCountry', 'title', 'description'] as $field) {
            $value = trim((string) ($target->get($field) ?? ''));
            if ($value === '') continue;
            if ($field === 'description') $value = mb_substr($value, 0, 1200);
            if (in_array($field, ['firstName', 'lastName'], true)) {
                if (!isset($values['name'])) $values['name'] = $value;
                continue;
            }
            $key = $field === 'title' ? 'role' : ($field === 'accountName' ? 'company' : ($field === 'addressCountry' || $field === 'billingAddressCountry' ? 'country' : ($field === 'description' ? 'publicBio' : $field)));
            $values[$key] = $value;
        }
        if ($profileUrl !== '') $values['profileUrl'] = $profileUrl;
        return OutreachEvidencePolicy::customerSnapshot($values);
    }

    private function targetFromEvidence(Entity $evidence): array
    {
        foreach (['lead', 'account', 'contact'] as $link) {
            $id = (string) ($evidence->get($link . 'Id') ?? '');
            if ($id !== '') return ['type' => ucfirst($link), 'id' => $id];
        }
        throw new BadRequest('Outreach evidence has no research target.');
    }

    public function assertOwner(Entity $evidence, User $user): void
    {
        if (!$user->isAdmin() && $evidence->get('assignedUserId') !== $user->getId()) throw new Forbidden('Evidence belongs to another user.');
    }

    public function enqueue(Entity $evidence, User $user): array
    {
        $this->assertOwner($evidence, $user);
        return $this->storage->locked(function () use ($evidence, $user) {
            $fresh = $this->repo('OutreachEvidence')->where(['id' => $evidence->getId()])->findOne();
            if (!$fresh) throw new NotFound('Evidence not found.');
            if (in_array($fresh->get('researchStatus'), ['completed', 'running', 'pending'], true)) return $this->view($fresh);
            if ((int) $fresh->get('researchAttempts') >= 3) throw new Conflict('Research attempt limit reached.');
            $fresh->set(['researchStatus' => 'pending', 'researchNextAt' => gmdate('Y-m-d H:i:s'), 'researchError' => null]);
            $this->kernel->save($fresh);
            $this->kernel->audit('outreach.research.queued', 'user', $user->getId(), 'OutreachEvidence', $fresh->getId());
            return $this->view($fresh);
        });
    }

    public function tick(): int
    {
        $now = gmdate('Y-m-d H:i:s');
        // A process may have died after a paid call; require a deliberate retry.
        foreach ($this->repo('OutreachEvidence')->where(['researchStatus' => 'running', 'researchNextAt<=' => $now])->limit(0, 10)->find() as $stale) {
            $stale->set(['researchStatus' => 'failed', 'researchError' => 'outreach_interrupted', 'researchNextAt' => null]);
            $this->kernel->save($stale);
        }
        $count = 0;
        foreach ($this->repo('OutreachEvidence')->where(['researchStatus' => ['pending', 'failed'], 'researchAttempts<' => 3, 'researchNextAt<=' => $now])->order('createdAt', 'ASC')->limit(0, 1)->find() as $evidence) {
            if (!$evidence->get('researchNextAt')) continue;
            $owner = $this->em->getEntityById('User', (string) $evidence->get('assignedUserId'));
            if (!$owner instanceof User || $owner->get('isActive') === false) continue;
            $this->research($evidence, $owner);
            $count++;
        }
        return $count;
    }

    private function boundedOptional(mixed $value, int $max): string
    {
        if ($value === null || $value === '') return '';
        if (!is_string($value) || trim($value) === '' || strlen($value) > $max) throw new BadRequest('Invalid bounded evidence field.');
        return trim($value);
    }

    private function repo(string $type) { return $this->em->getRDBRepository($type); }
}
