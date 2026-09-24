<?php
namespace Espo\Custom\Hooks\ExternalChannel;
use Espo\Core\Exceptions\Forbidden;
use Espo\Core\Hook\Hook\BeforeSave;
use Espo\ORM\Entity;
use Espo\ORM\Repository\Option\SaveOptions;
final class HistoryCoverageGuard implements BeforeSave
{
    public function beforeSave(Entity $entity, SaveOptions $options): void
    {
        if (!$options->get('fusanheInsights') && $entity->isAttributeChanged('historyCoverage') && $entity->get('historyCoverage') !== null) throw new Forbidden('History coverage is set by reconciliation only.');
    }
}
