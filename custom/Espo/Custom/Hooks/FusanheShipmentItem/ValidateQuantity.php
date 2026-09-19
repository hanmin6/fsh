<?php
namespace Espo\Custom\Hooks\FusanheShipmentItem;

use Espo\Core\Exceptions\Conflict;
use Espo\Core\Hook\Hook\BeforeSave;
use Espo\ORM\Entity;
use Espo\ORM\Repository\Option\SaveOptions;

/**
 * Anti-over-shipment: the shipped quantity per order line (excluding
 * cancelled shipments) can never exceed the ordered quantity, and the unit
 * must match the ordered unit. Without a recorded quantity there is no
 * coverage claim, so this fails loudly instead of pretending.
 */
class ValidateQuantity implements BeforeSave
{
    public function __construct(private \Espo\ORM\EntityManager $em) {}

    public function beforeSave(Entity $entity, SaveOptions $options): void
    {
        $orderLineId = $entity->get('orderLineId');
        if (!$orderLineId) {
            return;
        }
        $line = $this->em->getEntityById('FusanheOrderLine', (string) $orderLineId);
        if (!$line) {
            throw new Conflict('Order line not found for this shipment item.');
        }
        if ((string) $entity->get('unit') !== (string) $line->get('unit')) {
            throw new Conflict('Shipment unit must match the ordered unit.');
        }
        $shipped = 0.0;
        foreach ($this->em->getRDBRepository('FusanheShipmentItem')
                     ->where(['orderLineId' => $orderLineId])->find() as $other) {
            if (!$entity->isNew() && $other->getId() === $entity->getId()) {
                continue;
            }
            $shipment = $this->em->getEntityById('FusanheOrderShipment', (string) $other->get('shipmentId'));
            if ($shipment && $shipment->get('status') === 'cancelled') {
                continue;
            }
            $shipped += (float) $other->get('quantity');
        }
        $total = $shipped + (float) $entity->get('quantity');
        if ($total > (float) $line->get('quantity') + 0.000001) {
            throw new Conflict(sprintf(
                'Over-shipment rejected: ordered %.2f %s, already shipped %.2f, this item %.2f.',
                (float) $line->get('quantity'), (string) $line->get('unit'), $shipped, (float) $entity->get('quantity')
            ));
        }
    }
}
