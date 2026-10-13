<?php
namespace Espo\Custom\Tools\Fusanhe;
use Espo\ORM\Entity;
use Espo\ORM\EntityManager;
use DateTimeImmutable;
use DateTimeZone;

/** Minute orchestration, source-message idempotency and execution-time revocation. */
final class ScheduledReceptionService
{
    public function __construct(private EntityManager $em, private ServiceKernel $kernel, private ReceptionReply $reply) {}
    public function customer(Entity $conversation): ?Entity
    {
        foreach (['lead' => 'Lead', 'account' => 'Account', 'contact' => 'Contact'] as $link => $type) {
            $id = $conversation->get($link . 'Id');
            if ($id && ($entity = $this->em->getRDBRepository($type)->where(['id' => $id])->findOne())) return $entity;
        }
        return null;
    }
    public function allowed(Entity $conversation, ?array $config = null): bool
    {
        // A customer-level pause also revokes legacy platform reception, including linked accounts.
        foreach (['lead'=>'Lead','account'=>'Account','contact'=>'Contact'] as $link=>$type) {
            $id=$conversation->get($link.'Id');$related=$id?$this->em->getRDBRepository($type)->where(['id'=>$id])->findOne():null;
            if ($related && (!empty(((array)($related->get('fusanheSalesProfile')??[]))['paused']) || $related->get('fusanheDoNotContact') || in_array($related->get('fusanheContactPolicy'),['optedOut','restricted'],true))) return false;
        }
        $customer = $this->customer($conversation);
        return ReceptionSchedule::allows((array) $conversation->getValueMap(), $customer ? (array) $customer->getValueMap() : null, $config ?? ReceptionSettings::read());
    }
    public function taskCanRun(Entity $task, Entity $conversation): bool
    {
        if ($task->get('triggerType') !== 'scheduledReception') return false;
        $channel = $this->em->getEntityById('ExternalChannel', (string) $task->get('channelId'));
        $channelConfig = (array) ($channel?->get('config') ?? []);
        if (!$channel || $channel->get('type') !== 'Alibaba' || empty($channelConfig['realOutbound']) || $task->get('executionMode') !== 'real' || $task->get('channelId') !== $conversation->get('channelId')) return false;
        $config = ReceptionSettings::read(); $payload = (array) ($task->get('payload') ?? []);
        if (($payload['receptionVersion'] ?? '') !== ReceptionReply::VERSION || ($payload['scheduleRevision'] ?? null) !== $config['revision'] || !$this->allowed($conversation, $config)) return false;
        $draft = $this->em->getEntityById('AIReplyDraft', (string) $task->get('replyDraftId'));
        if (!$draft || $draft->get('modelName') !== 'gpt-6.1-sol') return false;
        $source = $this->em->getRDBRepository('ExternalMessage')->where(['id' => $payload['sourceMessageId'] ?? '', 'conversationId' => $conversation->getId(), 'direction' => 'inbound'])->findOne();
        if (!$source || !$this->fresh($source, $config)) return false;
        $latest = $this->latestInbound($conversation);
        // A new buyer message or a human/platform outbound supersedes this reply.
        return $latest && $latest->getId() === $source->getId() && !$this->alreadyAnswered($conversation, $source);
    }
    private function latestInbound(Entity $conversation): ?Entity
    {
        return $this->em->getRDBRepository('ExternalMessage')->where(['conversationId' => $conversation->getId(), 'direction' => 'inbound'])->order('sentAt', 'DESC')->order('createdAt', 'DESC')->findOne();
    }
    private function alreadyAnswered(Entity $conversation, Entity $message): bool
    {
        return (bool) $this->em->getRDBRepository('ExternalMessage')->where(['conversationId' => $conversation->getId(), 'direction' => 'outbound', 'sentAt>=' => $message->get('sentAt')])->findOne();
    }
    public function fresh(Entity $message, array $config): bool
    {
        $sent = (string) $message->get('sentAt'); $created = (string) $message->get('createdAt');
        if (!$config['activatedAt'] || $sent < $config['activatedAt'] || $created < $config['activatedAt'] || !in_array($message->get('timestampConfidence'), ['high', 'medium'], true)) return false;
        $instant = new DateTimeImmutable($sent, new DateTimeZone('UTC'));
        $age = time() - $instant->getTimestamp();
        // Fresh arrival only; no stale backlog/backfill and no replies to working-hours inquiries.
        return $age >= 0 && $age <= 1800 && ReceptionSchedule::state($config, $instant)['active'];
    }
    public function tick(): array
    {
        $dir = ReceptionSettings::directory();
        $lock = fopen($dir . '/auto-reply-tick.lock', 'c');
        if (!$lock) throw new \RuntimeException('Reception tick lock unavailable.');
        ReceptionSettings::protect($dir . '/auto-reply-tick.lock', 0600);
        if (!flock($lock, LOCK_EX | LOCK_NB)) { fclose($lock); return ['busy' => true]; }
        try {
            $config = ReceptionSettings::read(); $made = 0; $cancelled = 0; $errors = 0;
            // Never retry a send with uncertain outcome. Only expire pre-send work.
            foreach ($this->em->getRDBRepository('OutboundTask')->where(['triggerType' => 'scheduledReception', 'status' => ['pending','claimed']])->find() as $task) {
                $conversation = $this->em->getEntityById('ExternalConversation', (string) $task->get('conversationId'));
                if (!$conversation || !$this->taskCanRun($task, $conversation)) {
                    $task->set(['status' => 'cancelled', 'errorMessage' => 'Scheduled reception expired, superseded or taken over.']); $this->kernel->save($task); $cancelled++;
                }
            }
            $this->handover($config);
            if (!ReceptionSchedule::state($config)['active']) return ['created' => 0, 'cancelled' => $cancelled, 'active' => false];
            // Internal work batch only, no daily customer quota. Next minute continues.
            foreach ($this->em->getRDBRepository('ExternalConversation')->where(['lastInboundAt>=' => gmdate('Y-m-d H:i:s', time() - 1800), 'status!=' => 'closed'])->order('lastInboundAt', 'ASC')->find() as $conversation) {
                if ($made >= 20) break;
                if (!$this->allowed($conversation, $config)) continue;
                $channel = $this->em->getEntityById('ExternalChannel', (string) $conversation->get('channelId'));
                // Enabled channel is explicit and limited to the logged-in Alibaba executor.
                if (!$channel || $channel->get('type') !== 'Alibaba') continue;
                $channelConfig = (array) ($channel->get('config') ?? []);
                if (empty($channelConfig['realOutbound'])) continue;
                $source = $this->latestInbound($conversation);
                if (!$source || !$this->fresh($source, $config) || $this->alreadyAnswered($conversation, $source)) continue;
                $key = hash('sha256', 'scheduledReception|' . $source->getId());
                if ($this->em->getRDBRepository('OutboundTask')->where(['idempotencyKey' => $key])->findOne()) continue;
                if ($this->em->getRDBRepository('OutboundTask')->where(['conversationId' => $conversation->getId(), 'status' => ['pending','claimed','sending']])->findOne()) continue;
                try {
                    $result = $this->reply->generate((string) $source->get('body'), (string) $conversation->get('language'));
                    // Model latency can cross a boundary or a takeover: fetch and recheck.
                    $conversation = $this->em->getRDBRepository('ExternalConversation')->where(['id' => $conversation->getId()])->findOne();
                    $current = ReceptionSettings::read();
                    if (!$conversation || $current['revision'] !== $config['revision'] || !$this->allowed($conversation, $current) || !$this->fresh($source, $current) || $this->alreadyAnswered($conversation, $source) || $this->latestInbound($conversation)?->getId() !== $source->getId()) continue;
                    $tx = $this->em->getTransactionManager(); $tx->start();
                    try {
                        $draft = $this->kernel->create('AIReplyDraft', ['name' => '非工作时间 AI 接待', 'conversationId' => $conversation->getId(), 'sourceMessageId' => $source->getId(), 'draftText' => $result['text'], 'intent' => $result['replyKey'], 'summaryZh' => '非工作时间收集需求，商务信息待人工确认。', 'suggestedLanguage' => $conversation->get('language') === 'zh' ? 'zh' : 'en', 'riskLevel' => 'low', 'confidence' => 1.0, 'missingInformation' => ['商务条款待人工确认'], 'citedKnowledge' => [], 'modelProvider' => $result['provider'], 'modelName' => $result['model'], 'usageTokens' => $result['usageTokens'], 'promptVersion' => ReceptionReply::VERSION, 'status' => 'approved', 'approvedAt' => $this->kernel->now()]);
                        $task = $this->kernel->create('OutboundTask', ['name' => '定时接待 ' . substr($key,0,10), 'conversationId' => $conversation->getId(), 'replyDraftId' => $draft->getId(), 'channelId' => $channel->getId(), 'status' => 'pending', 'idempotencyKey' => $key, 'triggerType' => 'scheduledReception', 'executionMode' => 'real', 'contentSnapshot' => $result['text'], 'payload' => ['body' => $result['text'], 'sourceMessageId' => $source->getId(), 'scheduleRevision' => $config['revision'], 'receptionVersion' => ReceptionReply::VERSION]]);
                        $conversation->set(['status' => 'readyToSend', 'scheduledReceptionMessageId' => $source->getId(), 'scheduledReceptionAt' => $this->kernel->now()]);
                        $customer = $this->customer($conversation);
                        if ($customer && in_array(AcquisitionRouting::effectiveRating((array) $customer->getValueMap()), ['S','A'], true) && $conversation->get('controlMode') !== 'human') $conversation->set(['controlMode' => 'human', 'controlOrigin' => 'valueRouting']);
                        $this->kernel->save($conversation);
                        $this->kernel->audit('reception.queued', 'system', 'schedule', 'OutboundTask', $task->getId(), 'success', ['sourceMessageId' => $source->getId(), 'revision' => $config['revision'], 'model' => $result['model']]);
                        $tx->commit(); $made++;
                    } catch (\Throwable $e) { $tx->rollback(); throw $e; }
                } catch (\Throwable $e) {
                    $errors++;
                    // Exception text may include transport payload: expose only its class.
                    $this->kernel->audit('reception.failed', 'system', 'schedule', 'ExternalConversation', $conversation?->getId() ?? 'unknown', 'failure', ['errorType' => get_class($e)]);
                }
            }
            return ['created' => $made, 'cancelled' => $cancelled, 'errors' => $errors, 'active' => true];
        } finally { flock($lock, LOCK_UN); fclose($lock); }
    }
    private function handover(array $config): void
    {
        if (ReceptionSchedule::state($config)['active']) return;
        foreach ($this->em->getRDBRepository('ExternalConversation')->where(['scheduledReceptionMessageId!=' => null])->find() as $conversation) {
            $customer = $this->customer($conversation);
            if (!$customer || !in_array(AcquisitionRouting::effectiveRating((array) $customer->getValueMap()), ['S','A'], true)) continue;
            $key = hash('sha256', 'scheduled-handover|' . $conversation->get('scheduledReceptionMessageId'));
            if (!$this->em->getRDBRepository('Task')->where(['fusanheHandoffKey' => $key])->findOne()) {
                $this->kernel->create('Task', ['name' => '接回高价值客户：' . mb_substr((string) $conversation->get('name'),0,60), 'status' => 'Not Started', 'priority' => 'High', 'parentType' => 'ExternalConversation', 'parentId' => $conversation->getId(), 'assignedUserId' => $conversation->get('assignedUserId'), 'fusanheHandoffKey' => $key, 'description' => 'AI 已处理非工作时间接待任务。请先核对发送结果和完整对话，再继续人工洽谈。', 'dateEnd' => gmdate('Y-m-d H:i:s', time() + 3600)]);
                $this->kernel->audit('reception.handover', 'system', 'schedule', 'ExternalConversation', $conversation->getId());
            }
            if ($conversation->get('controlMode') !== 'human') {
                $conversation->set(['controlMode' => 'human', 'controlOrigin' => 'valueRouting']); $this->kernel->save($conversation);
            }
        }
    }
}
