<?php
namespace Espo\Custom\Hooks\ExternalConversation;

use Espo\Core\Exceptions\Forbidden;
use Espo\Core\Hook\Hook\BeforeSave;
use Espo\ORM\Entity;
use Espo\ORM\Repository\Option\SaveOptions;

final class InsightsGuard implements BeforeSave
{
    public function beforeSave(Entity $entity, SaveOptions $options): void
    {
        if ($options->get('fusanheInsights')) return;
        foreach (['insightsStatus', 'insightsVersion', 'insightsModel', 'insightsAt', 'insightsError', 'insightsData'] as $field) {
            if ($entity->isNew() && ($entity->get($field) === null || ($field === 'insightsStatus' && $entity->get($field) === 'pending'))) continue;
            if ($entity->isAttributeChanged($field)) throw new Forbidden('History insights are managed by the analysis worker.');
        }
    }
}
