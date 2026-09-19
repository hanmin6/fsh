<?php
namespace Espo\Custom\Hooks\FusanheSalesOrder;

use Espo\Core\Exceptions\Conflict;
use Espo\Core\Exceptions\Forbidden;
use Espo\Core\Hook\Hook\BeforeSave;
use Espo\ORM\Entity;
use Espo\ORM\Repository\Option\SaveOptions;

/**
 * Order numbers unique/immutable; status only via endpoints; once confirmed,
 * the quote snapshot and confirmed delivery date are frozen.
 */
class GuardAndNumber implements BeforeSave
{
    private const FROZEN_AFTER_CONFIRM = [
        'quoteId', 'accountId', 'contactId', 'currency', 'tradeTerm', 'tradeTermPlace',
        'tradeTermVersion', 'paymentTerms', 'leadTimeText', 'exchangeRate',
        'exchangeRateDate', 'exchangeRateSource', 'quoteAcceptedAt', 'quoteAcceptedByRef',
        'internalConfirmedDate',
    ];

    public function __construct(private \Espo\ORM\EntityManager $em) {}

    public function beforeSave(Entity $entity, SaveOptions $options): void
    {
        if ($entity->isNew()) {
            if (!$entity->get('number')) {
                $entity->set('number', 'SO-' . date('YmdHis') . '-' . substr(bin2hex(random_bytes(3)), 0, 5));
            } else {
                $this->assertNumberFree($entity);
            }
            return;
        }
        if ($entity->isAttributeChanged('number')) {
            throw new Forbidden('Order numbers are immutable.');
        }
        if (\Espo\Custom\Tools\Fusanhe\InternalWrite::isFlagged()) {
            return;
        }
        if ($entity->isAttributeChanged('status')) {
            throw new Forbidden('Order status changes go through the Fusanhe endpoints.');
        }
        if ($entity->getFetched('status') === 'confirmed') {
            foreach (self::FROZEN_AFTER_CONFIRM as $attribute) {
                if ($entity->isAttributeChanged($attribute)) {
                    throw new Forbidden('Confirmed orders keep the quote snapshot frozen; cancel and re-create instead.');
                }
            }
        }
    }

    private function assertNumberFree(Entity $entity): void
    {
        $query = $this->em->getRDBRepository('FusanheSalesOrder')
            ->where(['number' => $entity->get('number')]);
        if ($entity->getId()) {
            $query->where(['id!=' => $entity->getId()]);
        }
        if ($query->findOne()) {
            throw new Conflict('Order number already exists.');
        }
    }
}
