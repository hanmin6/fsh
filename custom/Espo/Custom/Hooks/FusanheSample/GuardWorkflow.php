<?php
namespace Espo\Custom\Hooks\FusanheSample;

use Espo\Core\Exceptions\Conflict;
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
        'status', 'trackingNo', 'sentAt', 'deliveredAt', 'returned',
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
            return;
        }
        if (!\Espo\Custom\Tools\Fusanhe\InternalWrite::isFlagged()) {
            foreach (self::GUARDED as $attribute) {
                if ($entity->isAttributeChanged($attribute)) {
                    throw new Conflict('Sample workflow fields can only change through the Fusanhe endpoints.');
                }
            }
        }
        if ($entity->isAttributeChanged('number')) {
            throw new Conflict('Sample numbers are immutable.');
        }
    }

    private function assertNumberFree(Entity $entity): void
    {
        $duplicate = $this->em->getRDBRepository('FusanheSample')
            ->where(['number' => $entity->get('number')])
            ->findOne();
        if ($duplicate) {
            throw new Conflict('Sample number already exists.');
        }
    }
}
