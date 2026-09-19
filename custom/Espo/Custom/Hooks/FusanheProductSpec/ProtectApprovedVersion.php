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
        if ($entity->isNew() || $entity->getFetched('status') !== 'approved') {
            return;
        }
        if ($entity->isAttributeChanged('status') && $entity->get('status') === 'retired') {
            return;
        }
        foreach (self::CONTENT_FIELDS as $attribute) {
            if ($entity->isAttributeChanged($attribute)) {
                throw new Forbidden('Approved spec versions are immutable; create a new version instead.');
            }
        }
    }
}
