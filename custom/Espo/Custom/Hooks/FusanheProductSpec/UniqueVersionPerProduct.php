<?php
namespace Espo\Custom\Hooks\FusanheProductSpec;

use Espo\Core\Exceptions\Conflict;
use Espo\Core\Hook\Hook\BeforeSave;
use Espo\ORM\Entity;
use Espo\ORM\Repository\Option\SaveOptions;

/**
 * A product cannot carry two spec rows with the same version label:
 * traceability depends on version identifiers being unambiguous.
 */
class UniqueVersionPerProduct implements BeforeSave
{
    public function __construct(private \Espo\ORM\EntityManager $em) {}

    public function beforeSave(Entity $entity, SaveOptions $options): void
    {
        $productId = $entity->get('productId');
        $version = $entity->get('version');
        if (!$productId || !$version) {
            return;
        }
        $duplicate = $this->em->getRDBRepository('FusanheProductSpec')
            ->where([
                'productId' => $productId,
                'version' => $version,
                'id!=' => $entity->isNew() ? null : $entity->getId(),
            ])
            ->findOne();
        if ($duplicate) {
            throw new Conflict('This version already exists for the product; use a new version label.');
        }
    }
}
