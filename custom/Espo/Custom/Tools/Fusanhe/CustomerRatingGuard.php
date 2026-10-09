<?php
namespace Espo\Custom\Tools\Fusanhe;
use Espo\Core\Exceptions\Forbidden;
use Espo\Core\Exceptions\BadRequest;
use Espo\Entities\User;
use Espo\ORM\Entity;
use Espo\ORM\Repository\Option\SaveOptions;
final class CustomerRatingGuard
{
    public function __construct(private User $user) {}
    public function beforeSave(Entity $entity, SaveOptions $options): void
    {
        if ($options->get('fusanheRating')) return;
        foreach (['aiRating','aiRatingReason','aiRatingAt','aiRatingModel','aiRatingData','aiRatingVersion','aiRatingError','aiRatingAttempts','aiRatingNextAt','aiCompanyName','ratingSource'] as $field) {
            if ($entity->isNew() && ($entity->get($field) === null || $entity->get($field) === '' || $entity->get($field) === 0)) continue;
            if ($entity->isAttributeChanged($field)) throw new Forbidden('Automatic rating fields are service-owned.');
        }
        if ($entity->isAttributeChanged('aiRatingStatus') && !($entity->isNew() && in_array($entity->get('aiRatingStatus'), [null, 'pending'], true))) throw new Forbidden('Automatic rating status is service-owned.');
        if (!$entity->isAttributeChanged('rating') && !$entity->isAttributeChanged('ratingReason')) {
            if (!$entity->isNew()) $entity->set(['ratingConfirmedAt'=>$entity->getFetched('ratingConfirmedAt'), 'ratingConfirmedById'=>$entity->getFetched('ratingConfirmedById')]);
            return;
        }
        $rating=(string)($entity->get('rating') ?? '');
        if ($rating !== '' && !isset(CustomerRatingPolicy::LEVELS[$rating])) throw new BadRequest('Invalid rating.');
        if ($rating !== '' && trim((string)$entity->get('ratingReason')) === '') throw new BadRequest('Rating rationale is required.');
        $entity->set(['ratingSource'=>'manual','ratingConfirmedAt'=>gmdate('Y-m-d H:i:s'),'ratingConfirmedById'=>$this->user->getId()]);
    }
}
