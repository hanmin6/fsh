<?php
namespace Espo\Custom\Hooks\FusanheQuote;

use Espo\Core\Exceptions\Conflict;
use Espo\Core\Exceptions\Forbidden;
use Espo\Core\Hook\Hook\BeforeSave;
use Espo\ORM\Entity;
use Espo\ORM\Repository\Option\SaveOptions;

/**
 * Quote numbers are unique and immutable. Quotes that were accepted by the
 * customer are frozen snapshots; only workflow endpoints may touch status.
 */
class GuardAndNumber implements BeforeSave
{
    public function __construct(private \Espo\ORM\EntityManager $em) {}

    public function beforeSave(Entity $entity, SaveOptions $options): void
    {
        if ($entity->isNew()) {
            if (!$entity->get('number')) {
                $entity->set('number', 'QT-' . date('YmdHis') . '-' . substr(bin2hex(random_bytes(3)), 0, 5));
            } else {
                $this->assertNumberFree($entity);
            }
            if (!\Espo\Custom\Tools\Fusanhe\InternalWrite::isFlagged() && ($entity->get('status') ?: 'draft') !== 'draft') {
                // Accepted/approved quotes can only exist through the endpoints.
                $entity->set(['status' => 'draft', 'acceptedAt' => null, 'acceptedByRef' => null]);
            }
            return;
        }
        if ($entity->isAttributeChanged('number')) {
            throw new Conflict('Quote numbers are immutable.');
        }
        if (!\Espo\Custom\Tools\Fusanhe\InternalWrite::isFlagged()) {
            if ($entity->isAttributeChanged('status')) {
                throw new Forbidden('Quote status changes go through the Fusanhe endpoints.');
            }
            if (in_array($entity->getFetched('status'), ['accepted', 'superseded'], true)) {
                foreach (['name', 'currency', 'validUntil', 'tradeTerm', 'tradeTermPlace',
                          'tradeTermVersion', 'paymentTerms', 'leadTimeText', 'exchangeRate',
                          'exchangeRateDate', 'exchangeRateSource', 'accountId', 'contactId',
                          'inquiryId', 'conversationId', 'sampleId', 'notesInternal',
                          'acceptedAt', 'acceptedByRef'] as $attribute) {
                    if ($entity->isAttributeChanged($attribute)) {
                        throw new Forbidden('Accepted or superseded quotes are immutable; create a new revision.');
                    }
                }
            }
        }
    }

    private function assertNumberFree(Entity $entity): void
    {
        $query = $this->em->getRDBRepository('FusanheQuote')
            ->where(['number' => $entity->get('number')]);
        // Exclude self: the afterSave root-id pass re-saves an already inserted row.
        if ($entity->getId()) {
            $query->where(['id!=' => $entity->getId()]);
        }
        if ($query->findOne()) {
            throw new Conflict('Quote number already exists.');
        }
    }
}
