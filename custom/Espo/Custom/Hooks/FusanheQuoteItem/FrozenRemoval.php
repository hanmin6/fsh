<?php
namespace Espo\Custom\Hooks\FusanheQuoteItem;

use Espo\Core\Exceptions\Forbidden;
use Espo\Core\Hook\Hook\BeforeRemove;
use Espo\ORM\Entity;
use Espo\ORM\Repository\Option\RemoveOptions;

class FrozenRemoval implements BeforeRemove
{
    private const FROZEN = ['accepted', 'superseded'];

    public function __construct(private \Espo\ORM\EntityManager $em) {}

    public function beforeRemove(Entity $entity, RemoveOptions $options): void
    {
        $quote = $this->em->getEntityById('FusanheQuote', (string) $entity->get('quoteId'));
        if ($quote && in_array($quote->get('status'), self::FROZEN, true)) {
            throw new Forbidden('Accepted or superseded quote snapshots cannot lose lines.');
        }
    }
}
