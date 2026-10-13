<?php
namespace Espo\Custom\Hooks\Lead;
use Espo\Core\Hook\Hook\BeforeSave;
use Espo\Core\Hook\Hook\AfterSave;
use Espo\ORM\Entity;
use Espo\ORM\Repository\Option\SaveOptions;
use Espo\Custom\Tools\Fusanhe\AcquisitionRoutingService;

final class RouteAcquisition implements BeforeSave, AfterSave
{
    public static int $order = 100;
    public function __construct(private AcquisitionRoutingService $service) {}
    public function beforeSave(Entity $entity, SaveOptions $options): void { $this->service->beforeLeadSave($entity); }
    public function afterSave(Entity $entity, SaveOptions $options): void { $this->service->afterLeadSave($entity); }
}
