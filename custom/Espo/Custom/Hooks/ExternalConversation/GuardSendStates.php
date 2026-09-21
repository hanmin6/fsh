<?php
namespace Espo\Custom\Hooks\ExternalConversation;

use Espo\Core\Exceptions\Forbidden;
use Espo\Core\Hook\Hook\BeforeSave;
use Espo\ORM\Entity;
use Espo\ORM\Repository\Option\SaveOptions;

/**
 * Conversation statuses that belong to the send workflow (readyToSend,
 * sending, sent) can only be reached through the Fusanhe flow. Humans may
 * still close or reopen conversations via generic CRUD.
 */
class GuardSendStates implements BeforeSave
{
    private const FLOW_STATES = ['readyToSend', 'sending', 'sent'];

    public function beforeSave(Entity $entity, SaveOptions $options): void
    {
        if ($entity->isNew()
            || $options->get('fusanheService')
            || \Espo\Custom\Tools\Fusanhe\InternalWrite::isFlagged()) {
            return;
        }
        if ($entity->isAttributeChanged('status')
            && in_array($entity->get('status'), self::FLOW_STATES, true)
            && in_array((string) $entity->getFetched('status'), ['new', 'pending', 'drafted', 'waitingApproval', 'closed', 'failed'], true)) {
            throw new Forbidden('Send-flow conversation states are managed by the Fusanhe workflow.');
        }
    }
}
