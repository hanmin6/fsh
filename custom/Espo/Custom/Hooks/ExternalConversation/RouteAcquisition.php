<?php
namespace Espo\Custom\Hooks\ExternalConversation;
use Espo\Core\Hook\Hook\BeforeSave;
use Espo\ORM\Entity;
use Espo\ORM\Repository\Option\SaveOptions;
use Espo\Custom\Tools\Fusanhe\AcquisitionRoutingService;

final class RouteAcquisition implements BeforeSave
{
    public static int $order = 100;
    public function __construct(private AcquisitionRoutingService $service) {}
    public function beforeSave(Entity $entity, SaveOptions $options): void { $this->service->beforeConversationSave($entity); }
}
