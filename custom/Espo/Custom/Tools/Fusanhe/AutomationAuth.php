<?php
namespace Espo\Custom\Tools\Fusanhe;

use Espo\Core\Api\Request;
use Espo\Core\Exceptions\Forbidden;
use Espo\ORM\EntityManager;

final class AutomationAuth
{
    private const PLACEHOLDER = 'replace-with-a-long-random-token';

    public function __construct(private EntityManager $em) {}

    /** The shared secret is only a bootstrap credential for registration. */
    public function assertBootstrap(Request $request): void
    {
        $expected = (string) getenv('FUSANHE_AUTOMATION_TOKEN');
        $actual = $this->token($request);
        if ($expected === '' || $expected === self::PLACEHOLDER || !hash_equals($expected, $actual)) {
            throw new Forbidden('Automation authentication failed.');
        }
    }

    /** Validate a per-agent credential and bind it to the declared agentKey. */
    public function assertAgent(Request $request, string $agentKey): void
    {
        $agentKey = trim($agentKey);
        $token = $this->token($request);
        if ($agentKey === '' || $token === '') {
            throw new Forbidden('Automation authentication failed.');
        }
        $agent = $this->em->getRDBRepository('AutomationAgent')
            ->where(['agentKey' => $agentKey])
            ->findOne();
        if (!$agent) {
            throw new Forbidden('Automation authentication failed.');
        }

        $hash = (string) ($agent->get('credentialHash') ?? '');
        $expiresAt = (string) ($agent->get('credentialExpiresAt') ?? '');
        $revokedAt = (string) ($agent->get('credentialRevokedAt') ?? '');
        $valid = $hash !== ''
            && $revokedAt === ''
            && ($expiresAt === '' || strtotime($expiresAt) > time())
            && password_verify($token, $hash);

        // Time-bounded migration only. Empty/expired cutoff disables fallback.
        if (!$valid && $hash === '' && $this->legacyAllowed()) {
            $legacy = (string) getenv('FUSANHE_AUTOMATION_TOKEN');
            $valid = $legacy !== '' && $legacy !== self::PLACEHOLDER && hash_equals($legacy, $token);
        }
        if (!$valid) {
            throw new Forbidden('Automation authentication failed.');
        }
        $agent->set('credentialLastUsedAt', gmdate('Y-m-d H:i:s'));
        $this->em->saveEntity($agent, ['skipHooks' => true]);
    }

    /** Issue a secret once; only its password hash is persisted. */
    public function issueCredential(string $agentKey): array
    {
        $agent = $this->em->getRDBRepository('AutomationAgent')
            ->where(['agentKey' => trim($agentKey)])
            ->findOne();
        if (!$agent) {
            throw new Forbidden('Automation authentication failed.');
        }
        $plain = rtrim(strtr(base64_encode(random_bytes(48)), '+/', '-_'), '=');
        $issuedAt = gmdate('Y-m-d H:i:s');
        $ttlDays = max(1, min(365, (int) (getenv('FUSANHE_AGENT_CREDENTIAL_TTL_DAYS') ?: 90)));
        $expiresAt = gmdate('Y-m-d H:i:s', time() + ($ttlDays * 86400));
        $version = ((int) ($agent->get('credentialVersion') ?? 0)) + 1;
        $agent->set([
            'credentialHash' => password_hash($plain, PASSWORD_DEFAULT),
            'credentialVersion' => $version,
            'credentialIssuedAt' => $issuedAt,
            'credentialExpiresAt' => $expiresAt,
            'credentialRevokedAt' => null,
            'credentialLastUsedAt' => null,
        ]);
        $this->em->saveEntity($agent, ['skipHooks' => true]);
        return [
            'credential' => $plain,
            'credentialVersion' => $version,
            'credentialExpiresAt' => $expiresAt,
        ];
    }

    public function revoke(string $agentKey): void
    {
        $agent = $this->em->getRDBRepository('AutomationAgent')->where(['agentKey' => trim($agentKey)])->findOne();
        if ($agent) {
            $agent->set('credentialRevokedAt', gmdate('Y-m-d H:i:s'));
            $this->em->saveEntity($agent, ['skipHooks' => true]);
        }
    }

    private function token(Request $request): string
    {
        return trim((string) ($request->getHeader('X-Automation-Token') ?? ''));
    }

    private function legacyAllowed(): bool
    {
        $cutoff = trim((string) (getenv('FUSANHE_AUTOMATION_LEGACY_UNTIL') ?: ''));
        return $cutoff !== '' && strtotime($cutoff . ' 23:59:59 UTC') >= time();
    }
}
