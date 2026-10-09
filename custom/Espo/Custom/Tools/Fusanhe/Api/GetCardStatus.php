<?php
namespace Espo\Custom\Tools\Fusanhe\Api;

use DateTimeImmutable;
use DateTimeZone;
use Espo\Core\Acl;
use Espo\Core\Api\Request;
use Espo\Core\Api\Response;
use Espo\Core\Select\SelectBuilderFactory;
use Espo\Custom\Tools\Fusanhe\CardProgress;
use Espo\Entities\User;
use Espo\ORM\EntityManager;

final class GetCardStatus extends AbstractFusanheAction
{
    public function __construct(User $user, Acl $acl, EntityManager $em,
        private SelectBuilderFactory $selectBuilderFactory)
    {
        parent::__construct($user, $acl, $em);
    }

    public function process(Request $request): Response
    {
        $this->requireScope('ExternalMessage', 'read');
        $this->requireScope('ExternalConversation', 'read');
        $now = new DateTimeImmutable('now', new DateTimeZone('UTC'));
        [$start, $end] = CardProgress::bounds($now);
        $events = [];
        $conversations = [];
        for ($offset = 0; ; $offset += 200) {
            $query = $this->selectBuilderFactory->create()->from('ExternalMessage')
                ->withStrictAccessControl()->buildQueryBuilder()
                ->where(['direction' => 'outbound', 'deliveryStatus' => ['sent', 'delivered'],
                    'sentAt>=' => $start->format('Y-m-d H:i:s'), 'sentAt<' => $end->format('Y-m-d H:i:s')])
                ->select(['id', 'conversationId', 'rawPayload', 'direction', 'deliveryStatus', 'sentAt'])
                ->order('id')->limit($offset, 200)->build();
            $rows = $this->em->getRDBRepository('ExternalMessage')->clone($query)->find();
            foreach ($rows as $message) {
                $payload = (array) ($message->get('rawPayload') ?? []);
                if (($payload['source'] ?? '') !== 'Muse') continue;
                $id = (string) $message->get('conversationId');
                if (!array_key_exists($id, $conversations)) {
                    $conversations[$id] = $this->em->getEntityById('ExternalConversation', $id);
                }
                $conversation = $conversations[$id];
                if (!$conversation || !$this->acl->checkEntity($conversation, 'read')) continue;
                $key = null;
                foreach (['accountId', 'contactId', 'leadId', 'identityId'] as $field) {
                    if ($conversation->get($field)) {
                        $key = $field . ':' . $conversation->get($field);
                        break;
                    }
                }
                $events[] = ['source' => 'Muse', 'customerKey' => $key,
                    'direction' => $message->get('direction'), 'deliveryStatus' => $message->get('deliveryStatus'),
                    'sentAt' => $message->get('sentAt')];
            }
            if (count($rows) < 200) break;
        }
        $connected = false;
        $lastCheckAt = null;
        if ($this->user->isAdmin() || $this->acl->checkScope('AutomationAgent', 'read')) {
            $query = $this->selectBuilderFactory->create()->from('AutomationAgent')
                ->withStrictAccessControl()->buildQueryBuilder()->where(['mode' => 'real'])->build();
            foreach ($this->em->getRDBRepository('AutomationAgent')->clone($query)->find() as $agent) {
                if (!in_array('MuseCRM', (array) ($agent->get('capabilities') ?? []), true)) continue;
                $heartbeat = (string) ($agent->get('lastHeartbeatAt') ?? '');
                if ($heartbeat !== '' && ($lastCheckAt === null || $heartbeat > $lastCheckAt)) $lastCheckAt = $heartbeat;
                $at = $heartbeat ? strtotime($heartbeat . ' UTC') : false;
                if ($agent->get('status') === 'online' && $agent->get('credentialStatus') !== 'revoked' &&
                    $at !== false && $at <= $now->getTimestamp() + 60 && $at >= $now->getTimestamp() - 300) {
                    $connected = true;
                }
            }
        }
        return $this->json($request, CardProgress::summarize($events, $now) +
            ['connected' => $connected, 'lastCheckAt' => $lastCheckAt]);
    }
}
