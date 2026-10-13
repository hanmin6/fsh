<?php
namespace Espo\Custom\Tools\Fusanhe;

use Espo\Core\Exceptions\BadRequest;
use Espo\Core\Exceptions\Forbidden;
use Espo\ORM\Entity;
use Espo\ORM\EntityManager;
use stdClass;

final class GatewayRecoveryService
{
    public function __construct(private EntityManager $em, private ServiceKernel $kernel, private TextGateway $text) {}

    public function execute(stdClass $input, Entity $agent): array
    {
        $capability = 'GatewayRecovery:' . ($input->channelType ?? '') . ':' . ($input->accountHandle ?? '');
        if (!in_array($capability, (array) $agent->get('capabilities'), true)) throw new Forbidden('Recovery account is outside this agent scope.');
        if (!in_array($input->channelType ?? '', ['Alibaba', 'MadeInChina'], true)) throw new BadRequest('Unsupported recovery channel.');
        $operation = $input->operation ?? '';
        if ($operation === 'observe') {
            $channel = $this->em->getRDBRepository('ExternalChannel')->where(['type' => $input->channelType, 'accountHandle' => $input->accountHandle])->findOne();
            $lastSuccess = $channel ? $channel->get('lastSyncAt') : null;
            if ($channel) {
                $last = $this->em->getRDBRepository('ExternalConversation')->where(['channelId' => $channel->getId(), 'lastSourceSyncAt!=' => null])->order('lastSourceSyncAt', 'DESC')->findOne();
                if ($last && (!$lastSuccess || $last->get('lastSourceSyncAt') > $lastSuccess)) $lastSuccess = $last->get('lastSourceSyncAt');
            }
            $collectorKey = (string) ($input->collectorKey ?? '');
            if (!in_array('GatewayRecoveryCollector:' . $input->channelType . ':' . $collectorKey, (array) $agent->get('capabilities'), true)) throw new Forbidden('Collector is outside recovery scope.');
            $collector = $this->em->getRDBRepository('AutomationAgent')->where(['agentKey' => $collectorKey])->findOne();
            $knownErrors = ['login_required', 'verification_required', 'pending_batch_conflict', 'sync_failed', 'source_sync_pending_or_failed', 'browser_unavailable', 'incomplete_history', 'gateway_or_sync_unavailable'];
            $code = $collector ? (string) $collector->get('lastError') : '';
            return ['collectorStatus' => $collector?->get('status') ?? 'offline', 'lastHeartbeatAt' => $collector?->get('lastHeartbeatAt'),
                'reasonCode' => in_array($code, $knownErrors, true) ? $code : ($code === '' ? 'healthy' : 'gateway_or_sync_unavailable'),
                'sourceAgeSeconds' => $lastSuccess ? min(31536000, max(0, time() - strtotime($lastSuccess . ' UTC'))) : 31536000];
        }
        if ($operation === 'plan') {
            $o = GatewayRecoveryPolicy::observation((array) ($input->observation ?? []));
            if (($input->channelType === 'Alibaba') !== ($o['worker'] === 'alibaba')) throw new BadRequest('Worker and channel disagree.');
            $allowed = GatewayRecoveryPolicy::actions($o);
            $result = $this->text->complete([
                ['role' => 'system', 'content' => '你是福三和抓取恢复 agent。只判断给定的结构化运行状态；不读取或索取密码、客户信息、网页内容，不输出代码或命令。输出 JSON {"action":"...","reasonZh":"简短中文原因"}，action 必须属于 allowedActions。健康选 wait，进程停止或 worker_unresponsive 且允许重启时选 restart_worker，普通登录失效且可用保存密码选 auto_login，有可重放原批次选 replay_pending，source_stale 且不在抓取且允许重试时选 retry_sync，验证码/二次验证、没有原批次或未知身份冲突选 needs_human。'],
                ['role' => 'user', 'content' => json_encode(['channelType' => $input->channelType, 'observation' => $o, 'allowedActions' => $allowed], JSON_UNESCAPED_UNICODE)],
            ], 'gpt', true, 1600);
            $plan = json_decode($result['content'], true);
            if (!is_array($plan) || !in_array($plan['action'] ?? '', $allowed, true)) throw new \RuntimeException('recovery_invalid_model_action');
            $response = ['action' => $plan['action'], 'reasonZh' => mb_substr((string) ($plan['reasonZh'] ?? ''), 0, 240),
                'model' => $result['model'], 'allowedActions' => $allowed];
            $this->kernel->audit('gatewayRecovery.plan', 'agent', $agent->getId(), 'AutomationAgent', $agent->getId(), 'success', $response + ['channelType' => $input->channelType]);
            return $response;
        }
        if ($operation === 'verify_batch') {
            if ($input->channelType !== 'MadeInChina') throw new BadRequest('Only MIC replay journals are supported.');
            $requestId = (string) ($input->batchRequestId ?? '');
            $hash = (string) ($input->payloadHash ?? '');
            if (!preg_match('/^[A-Za-z0-9][A-Za-z0-9._:-]{0,63}$/D', $requestId) || !preg_match('/^[a-f0-9]{64}$/D', $hash)) throw new BadRequest('Invalid batch identity.');
            $audit = $this->em->getRDBRepository('AutomationAudit')->where(['requestId' => $requestId])->findOne();
            if (!$audit) return ['state' => 'not_confirmed'];
            $details = (array) $audit->get('details');
            if ($audit->get('eventType') !== 'madeInChina.sync.request' || $audit->get('result') !== 'success'
                || ($details['accountHandle'] ?? '') !== $input->accountHandle) throw new Forbidden('Batch is outside this recovery scope.');
            return ['state' => isset($details['payloadHash']) && hash_equals($hash, (string) $details['payloadHash']) ? 'accepted' : 'mismatch', 'batchRequestId' => $requestId];
        }
        if ($operation === 'report') {
            $action = (string) ($input->action ?? ''); $code = (string) ($input->resultCode ?? '');
            if (!in_array($action, ['restart_worker', 'auto_login', 'replay_pending', 'retry_sync', 'needs_human', 'wait'], true)
                || !preg_match('/^[a-z][a-z0-9_]{0,79}$/D', $code)) throw new BadRequest('Invalid recovery report.');
            $result = $action !== 'needs_human' && in_array($code, ['observing', 'browser_recovery_queued', 'worker_started', 'batch_replay_confirmed', 'healthy_verified'], true) ? 'success' : 'failure';
            $this->kernel->audit('gatewayRecovery.result', 'agent', $agent->getId(), 'AutomationAgent', $agent->getId(), $result, ['channelType' => $input->channelType, 'action' => $action, 'resultCode' => $code]);
            return ['recorded' => true];
        }
        throw new BadRequest('Unknown recovery operation.');
    }
}
