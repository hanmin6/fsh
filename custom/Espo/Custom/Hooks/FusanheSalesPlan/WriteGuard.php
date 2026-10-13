<?php
namespace Espo\Custom\Hooks\FusanheSalesPlan;
use Espo\Core\Exceptions\Forbidden;
use Espo\Core\Hook\Hook\BeforeSave;
use Espo\ORM\Entity;
use Espo\ORM\Repository\Option\SaveOptions;
final class WriteGuard implements BeforeSave
{
    public function beforeSave(Entity $entity,SaveOptions $options): void {if (!$options->get('fusanheService'))throw new Forbidden('Sales plans are changed through the sales service.');}
    public function beforeRemove(Entity $entity,$options): void {throw new Forbidden('Sales plans retain delivery history.');}
}
