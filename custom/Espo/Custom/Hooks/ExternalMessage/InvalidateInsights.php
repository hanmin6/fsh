<?php
namespace Espo\Custom\Hooks\ExternalMessage;
use Espo\Core\Hook\Hook\AfterSave;
use Espo\ORM\Entity;
use Espo\ORM\EntityManager;
use Espo\ORM\Repository\Option\SaveOptions;
final class InvalidateInsights implements AfterSave
{
    public function __construct(private EntityManager $em) {}
    public function afterSave(Entity $entity, SaveOptions $options): void
    {
        if (!$entity->isNew() && !$entity->isAttributeChanged('body') && !$entity->isAttributeChanged('sentAt') && !$entity->isAttributeChanged('direction')) return;
        $id = $entity->get('conversationId');
        $c = $id ? $this->em->getEntityById('ExternalConversation', $id) : null;
        if (!$c || !in_array($c->get('insightsStatus'), ['completed', 'failed'], true)) return;
        $c->set(['insightsStatus' => 'stale', 'insightsError' => null]);
        $this->em->saveEntity($c, ['fusanheInsights' => true, 'fusanheService' => true]);
    }
}
