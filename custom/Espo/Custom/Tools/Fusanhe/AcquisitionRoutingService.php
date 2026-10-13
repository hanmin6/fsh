<?php
namespace Espo\Custom\Tools\Fusanhe;

use Espo\Core\Exceptions\Conflict;
use Espo\ORM\Entity;
use Espo\ORM\EntityManager;

/** Persist acquisition ownership and enforce it at the existing execution boundary. */
final class AcquisitionRoutingService
{
    public function __construct(private EntityManager $em) {}

    public function snapshot(Entity $lead): array
    {
        $customer = [];
        foreach (AcquisitionRouting::FIELDS as $field) $customer[$field] = $lead->get($field);
        return $customer;
    }

    public function beforeLeadSave(Entity $lead): void
    {
        $customer = $this->snapshot($lead);
        if (!AcquisitionRouting::isAcquisition($customer)) return;
        $route = AcquisitionRouting::route($customer);
        $reason = AcquisitionRouting::reason($customer);
        if ($lead->get('fusanheFollowUpRoute') !== $route || $lead->get('fusanheFollowUpReason') !== $reason || !$lead->get('fusanheFollowUpRoutedAt')) {
            $lead->set(['fusanheFollowUpRoute' => $route, 'fusanheFollowUpReason' => $reason, 'fusanheFollowUpRoutedAt' => gmdate('Y-m-d H:i:s')]);
        }
    }

    /** Safe backfill entry point; does not create drafts, tasks or contact customers. */
    public function persist(Entity $lead): string
    {
        $this->beforeLeadSave($lead);
        if (AcquisitionRouting::isAcquisition($this->snapshot($lead))) {
            $this->em->saveEntity($lead, ['fusanheService' => true, 'fusanheAcquisitionRouting' => true]);
            $this->afterLeadSave($lead);
        }
        return AcquisitionRouting::route($this->snapshot($lead));
    }

    public function afterLeadSave(Entity $lead): void
    {
        $customer = $this->snapshot($lead);
        if (!AcquisitionRouting::isAcquisition($customer) || !in_array(AcquisitionRouting::route($customer), ['human', 'blocked'], true)) return;
        // Promotion stops existing automatic conversations. Never undo an
        // existing human takeover when a customer is later downgraded.
        foreach ($this->em->getRDBRepository('ExternalConversation')->where(['leadId' => $lead->getId(), 'controlMode' => 'aiAssist'])->find() as $conversation) {
            $conversation->set(['controlMode' => 'human', 'controlOrigin' => 'valueRouting']);
            $this->em->saveEntity($conversation, ['fusanheService' => true, 'fusanheAcquisitionRouting' => true]);
        }
    }

    public function beforeConversationSave(Entity $conversation): void
    {
        $lead = $this->conversationLead($conversation);
        if (!$lead || !AcquisitionRouting::isAcquisition($this->snapshot($lead))) return;
        $route = AcquisitionRouting::route($this->snapshot($lead));
        if (!in_array($route, ['human', 'blocked'], true) || $conversation->get('controlMode') === 'human') return;
        if (!$conversation->isNew() && $conversation->getFetched('controlMode') === 'human' && $conversation->isAttributeChanged('controlMode')) {
            throw new Conflict('Acquisition follow-up route is ' . $route . '; automatic control cannot resume.');
        }
        $conversation->set(['controlMode' => 'human', 'controlOrigin' => 'valueRouting']);
    }

    /** Recompute from the current Lead; persisted route is only a query/UI index. */
    public function taskCanRun(Entity $conversation): bool
    {
        if ($conversation->get('controlMode') === 'human') return false;
        $lead = $this->conversationLead($conversation);
        if (!$lead || !AcquisitionRouting::isAcquisition($this->snapshot($lead))) return true;
        return AcquisitionRouting::route($this->snapshot($lead)) === 'ai';
    }

    public function assertTaskCanRun(Entity $conversation): void
    {
        if (!$this->taskCanRun($conversation)) throw new Conflict('Acquisition follow-up is not assigned to AI or conversation is under human takeover.');
    }

    private function conversationLead(Entity $conversation): ?Entity
    {
        $id = (string) ($conversation->get('leadId') ?? '');
        // Query the repository again so a manual rating changed since claim
        // is observed before the task is handed to the external channel.
        return $id !== '' ? $this->em->getRDBRepository('Lead')->where(['id' => $id])->findOne() : null;
    }
}
