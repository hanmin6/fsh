<?php
namespace Espo\Custom\Hooks\Lead;
use Espo\Core\Hook\Hook\BeforeSave;
use Espo\Core\Exceptions\BadRequest;
use Espo\Entities\User;
use Espo\ORM\Entity;
use Espo\ORM\Repository\Option\SaveOptions;
class RecordRating implements BeforeSave
{
    public function __construct(private User $user) {}
    public function beforeSave(Entity $entity, SaveOptions $options): void
    {
        if (!$entity->isAttributeChanged('rating') && !$entity->isAttributeChanged('ratingReason')) {
            // Confirmation stamps are server-owned, including direct ORM saves.
            if (!$entity->isNew()) {
                $entity->set('ratingConfirmedAt', $entity->getFetched('ratingConfirmedAt'));
                $entity->set('ratingConfirmedById', $entity->getFetched('ratingConfirmedById'));
            }
            return;
        }
        $rating = (string) ($entity->get('rating') ?? '');
        if (!in_array($rating, ['', 'S', 'A', 'B', 'C'], true)) throw new BadRequest('Invalid rating.');
        if ($rating !== '' && trim((string) $entity->get('ratingReason')) === '') throw new BadRequest('Rating rationale is required.');
        $entity->set(['ratingConfirmedAt' => gmdate('Y-m-d H:i:s'), 'ratingConfirmedById' => $this->user->getId()]);
    }
}
