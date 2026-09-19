<?php
namespace Espo\Custom\Hooks\FusanheSample;

use Espo\Core\Exceptions\Conflict;
use Espo\Core\Exceptions\Forbidden;
use Espo\Core\Hook\Hook\BeforeSave;
use Espo\ORM\Entity;
use Espo\ORM\Repository\Option\SaveOptions;

/**
 * Guard rails for generic CRUD on samples: the status machine is driven by
 * dedicated endpoints only, and sample numbers stay unique and immutable.
 */
class GuardWorkflow implements BeforeSave
{
    private const GUARDED = [
        'status', 'trackingNo', 'trackingCarrier', 'sentAt', 'deliveredAt', 'returned',
        'returnedAt', 'returnNote', 'exceptionNote', 'feedback',
        'feedbackAt', 'feedbackResult', 'cancelReason',
    ];

    public function __construct(private \Espo\ORM\EntityManager $em) {}

    public function beforeSave(Entity $entity, SaveOptions $options): void
    {
        if ($entity->isNew()) {
            if (!$entity->get('number')) {
                $entity->set('number', 'SMP-' . date('YmdHis') . '-' . substr(bin2hex(random_bytes(3)), 0, 5));
            } else {
                $this->assertNumberFree($entity);
            }
            if (!\Espo\Custom\Tools\Fusanhe\InternalWrite::isFlagged()) {
                // The state machine starts at requested and only moves via endpoints.
                if (($entity->get('status') ?: 'requested') !== 'requested') {
                    $entity->set('status', 'requested');
                }
                foreach (self::GUARDED as $attribute) {
                    if ($attribute === 'status' || $attribute === 'feedbackResult') {
                        continue; // status stays requested; enum default applies
                    }
                    $entity->set($attribute, $attribute === 'returned' ? false : null);
                }
            }
            return;
        }
        if (!\Espo\Custom\Tools\Fusanhe\InternalWrite::isFlagged()) {
            foreach (self::GUARDED as $attribute) {
                if ($entity->isAttributeChanged($attribute)) {
                    throw new Forbidden('Sample workflow fields can only change through the Fusanhe endpoints.');
                }
            }
        }
        if ($entity->isAttributeChanged('number')) {
            throw new Forbidden('Sample numbers are immutable.');
        }
    }

    private function assertNumberFree(Entity $entity): void
    {
        $query = $this->em->getRDBRepository('FusanheSample')
            ->where(['number' => $entity->get('number')]);
        if ($entity->getId()) {
            $query->where(['id!=' => $entity->getId()]);
        }
        if ($query->findOne()) {
            throw new Conflict('Sample number already exists.');
        }
    }
}
