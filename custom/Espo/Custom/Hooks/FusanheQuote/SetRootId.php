<?php
namespace Espo\Custom\Hooks\FusanheQuote;

use Espo\Core\Hook\Hook\AfterSave;
use Espo\ORM\Entity;
use Espo\ORM\Repository\Option\SaveOptions;

/**
 * The version chain root defaults to the quote itself. Assigned after save
 * because the entity id only exists once persisted; re-entry stops because
 * the entity is no longer new on the nested save.
 */
class SetRootId implements AfterSave
{
    public function __construct(private \Espo\ORM\EntityManager $em) {}

    public function afterSave(Entity $entity, SaveOptions $options): void
    {
        if (!$entity->isNew() || $entity->get('rootId')) {
            return;
        }
        $entity->set('rootId', $entity->getId());
        \Espo\Custom\Tools\Fusanhe\InternalWrite::flag();
        $this->em->saveEntity($entity);
        \Espo\Custom\Tools\Fusanhe\InternalWrite::clear();
    }
}
