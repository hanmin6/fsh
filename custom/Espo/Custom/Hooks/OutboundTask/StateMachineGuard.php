<?php
namespace Espo\Custom\Hooks\OutboundTask;

use Espo\Core\Exceptions\Forbidden;
use Espo\Core\Hook\Hook\BeforeSave;
use Espo\ORM\Entity;
use Espo\ORM\Repository\Option\SaveOptions;

/**
 * Outbound tasks are created and mutated only by service actions (approve,
 * agent claim/sending/result, cancel). Plain record CRUD cannot forge a task,
 * bypass approval, or fake send results. Services pass the fusanheService
 * save option to bypass.
 */
class StateMachineGuard implements BeforeSave
{
    private const GUARDED_ATTRIBUTES = [
        'status',
        'idempotencyKey',
        'claimedBy',
        'claimedAt',
        'claimExpiresAt',
        'retryCount',
        'errorMessage',
        'platformMessageId',
        'completedAt',
        'payload',
        'contentSnapshot',
        'executionMode',
        'conversationId',
        'channelId',
        'replyDraftId',
    ];

    public function beforeSave(Entity $entity, SaveOptions $options): void
    {
        if ($options->get('fusanheService')) {
            return;
        }
        if ($entity->isNew()) {
            throw new Forbidden('Outbound tasks can only be created by the audited approval action.');
        }
        foreach (self::GUARDED_ATTRIBUTES as $attribute) {
            if ($entity->has($attribute) && $entity->isAttributeChanged($attribute)) {
                throw new Forbidden('Outbound task state is managed by service actions only.');
            }
        }
    }
}
