<?php
namespace Espo\Custom\Hooks\AIReplyDraft;

use Espo\Core\Exceptions\Forbidden;
use Espo\Core\Hook\Hook\BeforeRemove;
use Espo\ORM\Entity;
use Espo\ORM\Repository\Option\RemoveOptions;

class NoRemovalAfterApproval implements BeforeRemove
{
    public function beforeRemove(Entity $entity, RemoveOptions $options): void
    {
        if (in_array($entity->get('status'), ['approved', 'sent'], true)) {
            throw new Forbidden('Approved or sent drafts are audit history and cannot be deleted.');
        }
    }
}
