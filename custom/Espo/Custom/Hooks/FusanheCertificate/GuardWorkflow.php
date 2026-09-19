<?php
namespace Espo\Custom\Hooks\FusanheCertificate;

use Espo\Core\Exceptions\Forbidden;
use Espo\Core\Hook\Hook\BeforeSave;
use Espo\ORM\Entity;
use Espo\ORM\Repository\Option\SaveOptions;

/**
 * Certificate review status may only move through the dedicated approve and
 * revoke endpoints (marked as internal writes). Generic CRUD cannot approve,
 * revoke or forge a reviewed certificate — an unreviewed certificate must
 * never back a customer reply.
 */
class GuardWorkflow implements BeforeSave
{
    public function beforeSave(Entity $entity, SaveOptions $options): void
    {
        $flagged = \Espo\Custom\Tools\Fusanhe\InternalWrite::isFlagged();
        if ($entity->isNew()) {
            if (!$flagged && ($entity->get('status') ?: 'draft') !== 'draft') {
                $entity->set(['status' => 'draft', 'reviewerId' => null, 'reviewedAt' => null]);
            }
            return;
        }
        if ($flagged) {
            return;
        }
        if ($entity->isAttributeChanged('status') || $entity->isAttributeChanged('reviewerId') || $entity->isAttributeChanged('reviewedAt')) {
            throw new Forbidden('Certificate review state changes go through the Fusanhe endpoints.');
        }
    }
}
