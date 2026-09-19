<?php
namespace Espo\Custom\Hooks\OutboundTask;

use Espo\Core\Exceptions\Forbidden;
use Espo\Core\Hook\Hook\BeforeRemove;
use Espo\ORM\Entity;
use Espo\ORM\Repository\Option\RemoveOptions;

class NoRemoval implements BeforeRemove
{
    public function beforeRemove(Entity $entity, RemoveOptions $options): void
    {
        throw new Forbidden('Outbound tasks are audit history and cannot be deleted.');
    }
}
