<?php
namespace Espo\Custom\Hooks\ExternalConversation;

use Espo\Core\Exceptions\Forbidden;
use Espo\Core\Hook\Hook\BeforeSave;
use Espo\ORM\Entity;
use Espo\ORM\Repository\Option\SaveOptions;

/**
 * Conversation send-related states and the control mode are service-owned:
 * send results are written by the task pipeline, human takeover must run
 * through the audited control action. Direct record CRUD can no longer set
 * sending/sent/failed/replied or flip controlMode. Services pass the
 * fusanheService save option to bypass.
 */
class StateMachineGuard implements BeforeSave
{
    private const SERVICE_ONLY_STATUSES = ['sending', 'sent', 'failed', 'replied'];

    public function beforeSave(Entity $entity, SaveOptions $options): void
    {
        if ($options->get('fusanheService')) {
            return;
        }
        foreach (['controlOrigin', 'scheduledReceptionMessageId', 'scheduledReceptionAt'] as $field) {
            if ($entity->has($field) && $entity->isAttributeChanged($field) && (!$entity->isNew() || $entity->get($field))) throw new Forbidden('Reception state is managed by service actions only.');
        }
        if ($entity->isNew()) {
            if (in_array($entity->get('status'), self::SERVICE_ONLY_STATUSES, true)) {
                throw new Forbidden('Send states are written by the send pipeline only.');
            }
            if ($entity->get('controlMode') === 'human') {
                throw new Forbidden('Human takeover must go through the audited control action.');
            }
            return;
        }
        if (
            $entity->isAttributeChanged('status') &&
            in_array($entity->get('status'), self::SERVICE_ONLY_STATUSES, true)
        ) {
            throw new Forbidden('Send states are written by the send pipeline only.');
        }
        if ($entity->has('controlMode') && $entity->isAttributeChanged('controlMode')) {
            throw new Forbidden('Control mode changes must go through the audited control action.');
        }
        if ($entity->has('identityId') && $entity->isAttributeChanged('identityId')) {
            throw new Forbidden('Identity mapping changes must go through the audited link action.');
        }
    }
}
