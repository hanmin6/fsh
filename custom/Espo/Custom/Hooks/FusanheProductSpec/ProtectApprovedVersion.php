<?php
namespace Espo\Custom\Hooks\FusanheProductSpec;

use Espo\Core\Exceptions\Forbidden;
use Espo\Core\Hook\Hook\BeforeSave;
use Espo\ORM\Entity;
use Espo\ORM\Repository\Option\SaveOptions;

/**
 * Approved spec versions are immutable traceability anchors: quotes and
 * samples reference them. Content changes require a NEW version; only the
 * retirement transition is allowed afterwards.
 */
class ProtectApprovedVersion implements BeforeSave
{
    private const CONTENT_FIELDS = [
        'name', 'version', 'productId', 'packingSpec', 'pricingUnit', 'netWeightKg',
        'grossWeightKg', 'cartonSpec', 'moq', 'moqUnit', 'ingredients',
        'allergenStatus', 'allergens', 'shelfLife', 'storageConditions', 'origin',
        'markets', 'customerVisibleNotes', 'internalNotes', 'effectiveFrom', 'effectiveTo',
    ];

    public function beforeSave(Entity $entity, SaveOptions $options): void
    {
        if ($entity->isNew()) {
            if (!\Espo\Custom\Tools\Fusanhe\InternalWrite::isFlagged() && ($entity->get('status') ?: 'draft') !== 'draft') {
                $entity->set('status', 'draft');
            }
            return;
        }
        $flagged = \Espo\Custom\Tools\Fusanhe\InternalWrite::isFlagged();
        if (!$flagged && $entity->isAttributeChanged('status')) {
            // Review transitions only via the endpoints; an approved version can
            // only leave the state machine through retirement.
            if ($entity->getFetched('status') === 'approved' && $entity->get('status') !== 'retired') {
                throw new Forbidden('Approved spec versions are immutable; create a new version instead.');
            }
            if ($entity->getFetched('status') !== 'approved') {
                throw new Forbidden('Spec review status changes go through the Fusanhe endpoints.');
            }
        }
        if ($entity->getFetched('status') !== 'approved') {
            return;
        }
        foreach (self::CONTENT_FIELDS as $attribute) {
            if ($entity->isAttributeChanged($attribute)) {
                throw new Forbidden('Approved spec versions are immutable; create a new version instead.');
            }
        }
    }
}
