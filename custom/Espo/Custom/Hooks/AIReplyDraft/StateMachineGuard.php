<?php
namespace Espo\Custom\Hooks\AIReplyDraft;

use Espo\Core\Exceptions\Forbidden;
use Espo\Core\Hook\Hook\BeforeSave;
use Espo\ORM\Entity;
use Espo\ORM\Repository\Option\SaveOptions;

/**
 * Keeps AIReplyDraft.state machine service-only: drafts become approved/sent
 * exclusively through the audited approve/task-result actions. Direct record
 * CRUD (REST PATCH/POST) can no longer forge an approval or rewrite an
 * approved reply. Services pass the fusanheService save option to bypass.
 */
class StateMachineGuard implements BeforeSave
{
    private const SERVICE_STATUSES = ['approved', 'sent'];

    public function beforeSave(Entity $entity, SaveOptions $options): void
    {
        if ($options->get('fusanheService')) {
            return;
        }
        if ($entity->isNew()) {
            if (in_array($entity->get('status'), self::SERVICE_STATUSES, true)) {
                throw new Forbidden('Draft status approved/sent can only be set by the review action.');
            }
            return;
        }
        if (in_array($entity->get('status'), self::SERVICE_STATUSES, true)) {
            if ($entity->isAttributeChanged('draftText')) {
                throw new Forbidden('Approved replies are immutable; create a new draft instead.');
            }
        }
        if ($entity->isAttributeChanged('status')) {
            $next = $entity->get('status');
            if (in_array($next, self::SERVICE_STATUSES, true)) {
                throw new Forbidden('Draft approval must go through the audited approve action.');
            }
            $previous = $entity->getFetchedValue('status');
            if (in_array($previous, self::SERVICE_STATUSES, true)) {
                throw new Forbidden('Approved drafts cannot be reopened through record editing.');
            }
        }
    }
}
