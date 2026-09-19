<?php
namespace Espo\Custom\Hooks\FusanheOrderShipment;

use Espo\Core\Exceptions\Forbidden;
use Espo\Core\Hook\Hook\BeforeSave;
use Espo\ORM\Entity;
use Espo\ORM\Repository\Option\SaveOptions;

class GuardAndNumber implements BeforeSave
{
    public function __construct(private \Espo\ORM\EntityManager $em) {}

    public function beforeSave(Entity $entity, SaveOptions $options): void
    {
        if ($entity->isNew()) {
            if (!$entity->get('number')) {
                $entity->set('number', 'SHP-' . date('YmdHis') . '-' . substr(bin2hex(random_bytes(3)), 0, 5));
            }
            return;
        }
        if ($entity->isAttributeChanged('number')) {
            throw new Forbidden('Shipment numbers are immutable.');
        }
        if (!\Espo\Custom\Tools\Fusanhe\InternalWrite::isFlagged() && $entity->isAttributeChanged('status')) {
            throw new Forbidden('Shipment status changes go through the Fusanhe endpoints.');
        }
    }
}
