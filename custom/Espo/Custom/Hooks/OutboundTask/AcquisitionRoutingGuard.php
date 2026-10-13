<?php
namespace Espo\Custom\Hooks\OutboundTask;
use Espo\Core\Exceptions\Conflict;
use Espo\Core\Hook\Hook\BeforeSave;
use Espo\ORM\Entity;
use Espo\ORM\EntityManager;
use Espo\ORM\Repository\Option\SaveOptions;
use Espo\Custom\Tools\Fusanhe\AcquisitionRoutingService;

final class AcquisitionRoutingGuard implements BeforeSave
{
    public static int $order = 100;
    public function __construct(private AcquisitionRoutingService $service, private EntityManager $em) {}
    public function beforeSave(Entity $entity, SaveOptions $options): void
    {
        if ((!$entity->isNew() && !$entity->isAttributeChanged('status')) || !in_array($entity->get('status'), ['claimed', 'sending'], true)) return;
        $conversation = $this->em->getEntityById('ExternalConversation', (string) $entity->get('conversationId'));
        if (!$conversation) throw new Conflict('Outbound conversation is missing.');
        if ($entity->get('triggerType') === 'scheduledReception') {
            $reception = new \Espo\Custom\Tools\Fusanhe\ScheduledReceptionService($this->em, new \Espo\Custom\Tools\Fusanhe\ServiceKernel($this->em), new \Espo\Custom\Tools\Fusanhe\ReceptionReply());
            if (!$reception->taskCanRun($entity, $conversation)) throw new Conflict('Scheduled reception is no longer allowed.');
        } else { $this->service->assertTaskCanRun($conversation); }
        // Completed delivery results remain recordable after a route change;
        // the guard acts before execution, never erasing actual message history.
    }
}
