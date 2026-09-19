<?php
namespace Espo\Custom\Hooks\FusanheOrderLine;

use Espo\Core\Exceptions\Forbidden;
use Espo\Core\Hook\Hook\BeforeRemove;
use Espo\Core\Hook\Hook\BeforeSave;
use Espo\ORM\Entity;
use Espo\ORM\Repository\Option\RemoveOptions;
use Espo\ORM\Repository\Option\SaveOptions;

/**
 * Order lines are snapshots of accepted quote lines. Once the order is
 * confirmed they cannot change or be deleted, so shipment totals stay true.
 */
class FrozenSnapshot implements BeforeSave, BeforeRemove
{
    private const FIELDS = [
        'orderId', 'position', 'productId', 'productSpecId', 'description',
        'quantity', 'unit', 'unitPrice', 'amount', 'packingSpec',
    ];

    public function __construct(private \Espo\ORM\EntityManager $em) {}

    public function beforeSave(Entity $entity, SaveOptions $options): void
    {
        if ($entity->isNew()) {
            return;
        }
        if ($this->isFrozen($entity) && !\Espo\Custom\Tools\Fusanhe\InternalWrite::isFlagged()) {
            foreach (self::FIELDS as $attribute) {
                if ($entity->isAttributeChanged($attribute)) {
                    throw new Forbidden('Confirmed order lines are a frozen quote snapshot.');
                }
            }
        }
    }

    public function beforeRemove(Entity $entity, RemoveOptions $options): void
    {
        if ($this->isFrozen($entity) && !\Espo\Custom\Tools\Fusanhe\InternalWrite::isFlagged()) {
            throw new Forbidden('Confirmed order lines cannot be deleted.');
        }
    }

    private function isFrozen(Entity $entity): bool
    {
        $order = $this->em->getEntityById('FusanheSalesOrder', (string) $entity->get('orderId'));
        return $order && in_array($order->get('status'), ['confirmed', 'completed'], true);
    }
}
