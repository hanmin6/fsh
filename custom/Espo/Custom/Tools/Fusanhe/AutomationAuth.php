<?php
namespace Espo\Custom\Tools\Fusanhe;

use DateTimeImmutable;
use DateTimeZone;
use Espo\Core\Api\Request;
use Espo\Core\Exceptions\Forbidden;
use Espo\ORM\Entity;
use Espo\ORM\EntityManager;

final class AutomationAuth
{
    public function __construct(
        private EntityManager $em,
        private ServiceKernel $kernel,
    ) {}

    /**
     * The shared bootstrap token is deliberately restricted to agent
     * registration and credential rotation.
     */
    public function assertBootstrap(Request $request): void
    {
        $expected = (string) getenv('FUSANHE_AUTOMATION_TOKEN');
        $actual = (string) ($request->getHeader('X-Automation-Token') ?? '');
        if ($expected === '' || $expected === 'replace-with-a-long-random-token' || !hash_equals($expected, $actual)) {
            throw new Forbidden('Invalid automation token.');
        }
    }

    public function assertAgent(Request $request): Entity
    {
        $agentKey = trim((string) ($request->getHeader('X-Agent-Key') ?? ''));
        $agentToken = (string) ($request->getHeader('X-Agent-Token') ?? '');
        $agent = $agentKey === ''
            ? null
            : $this->em->getRDBRepository('AutomationAgent')
                ->where(['agentKey' => $agentKey])
                ->findOne();

        $credentialHash = $agent ? (string) ($agent->get('credentialHash') ?? '') : '';
        if (
            !$agent ||
            $agent->get('credentialStatus') !== 'active' ||
            $credentialHash === '' ||
            !password_verify($agentToken, $credentialHash)
        ) {
            throw new Forbidden('Invalid agent credential.');
        }

        $now = new DateTimeImmutable('now', new DateTimeZone('UTC'));
        $lastUsedAt = trim((string) ($agent->get('lastCredentialUsedAt') ?? ''));
        $shouldRecordUse = $lastUsedAt === '';
        if (!$shouldRecordUse) {
            try {
                $lastUsed = new DateTimeImmutable($lastUsedAt, new DateTimeZone('UTC'));
                $shouldRecordUse = $lastUsed <= $now->sub(new \DateInterval('PT5M'));
            } catch (\Exception) {
                $shouldRecordUse = true;
            }
        }
        if ($shouldRecordUse) {
            $agent->set('lastCredentialUsedAt', $now->format('Y-m-d H:i:s'));
            $this->kernel->save($agent);
        }

        return $agent;
    }
}
