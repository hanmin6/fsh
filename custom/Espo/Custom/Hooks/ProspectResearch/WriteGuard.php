<?php
namespace Espo\Custom\Hooks\ProspectResearch;
use Espo\Core\Exceptions\Forbidden;
use Espo\Core\Hook\Hook\BeforeSave;
use Espo\ORM\Entity;
use Espo\ORM\Repository\Option\SaveOptions;
final class WriteGuard implements BeforeSave
{
    public function beforeSave(Entity $entity, SaveOptions $options): void
    {
        if (!$options->get('fusanheService')) throw new Forbidden('Outreach records are changed through the dedicated outreach APIs.');
    }
    public function beforeRemove(Entity $entity, $options): void
    {
        throw new Forbidden('Outreach records retain their submission and asset history.');
    }
}
