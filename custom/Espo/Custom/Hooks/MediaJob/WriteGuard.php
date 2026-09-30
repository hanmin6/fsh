<?php
namespace Espo\Custom\Hooks\MediaJob;
use Espo\Core\Exceptions\Forbidden;
use Espo\Core\Hook\Hook\BeforeSave;
use Espo\ORM\Entity;
use Espo\ORM\Repository\Option\SaveOptions;
final class WriteGuard implements BeforeSave
{
    public function beforeSave(Entity $entity, SaveOptions $options): void
    {
        if (!$options->get('fusanheService')) throw new Forbidden('Creative records are changed through the dedicated creative APIs.');
    }
    public function beforeRemove(Entity $entity, $options): void
    {
        throw new Forbidden('Creative records retain their submission and asset history.');
    }
}
