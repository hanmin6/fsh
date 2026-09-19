<?php
namespace Espo\Custom\Hooks\ExternalMessage;

use Espo\Core\Exceptions\Forbidden;
use Espo\Core\Hook\Hook\BeforeSave;
use Espo\ORM\Entity;
use Espo\ORM\Repository\Option\SaveOptions;

/**
 * Outbound messages are receipts written by the send pipeline (with mock
 * receipts explicitly marked). Direct record CRUD cannot fabricate outbound
 * traffic or move a message between conversations. Services pass the
 * fusanheService save option to bypass.
 */
class WriteGuard implements BeforeSave
{
    public function beforeSave(Entity $entity, SaveOptions $options): void
    {
        if ($options->get('fusanheService')) {
            return;
        }
        if ($entity->isNew()) {
            if ($entity->get('direction') === 'outbound') {
                throw new Forbidden('Outbound messages are written by the send pipeline only.');
            }
            return;
        }
        foreach (['direction', 'conversationId', 'contentHash'] as $attribute) {
            if ($entity->has($attribute) && $entity->isAttributeChanged($attribute)) {
                throw new Forbidden('Message routing and identity are immutable.');
            }
        }
    }
}
