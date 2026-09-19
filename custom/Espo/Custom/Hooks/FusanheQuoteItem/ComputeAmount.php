<?php
namespace Espo\Custom\Hooks\FusanheQuoteItem;

use Espo\Core\Exceptions\Conflict;
use Espo\Core\Hook\Hook\BeforeSave;
use Espo\ORM\Entity;
use Espo\ORM\Repository\Option\SaveOptions;

/**
 * Line amounts are server-computed with a single documented rounding rule
 * (half-up, 2 decimals). Parent quote must stay editable; frozen parents
 * reject new or changed lines.
 */
class ComputeAmount implements BeforeSave
{
    private const FROZEN = ['accepted', 'superseded'];

    public function __construct(private \Espo\ORM\EntityManager $em) {}

    public function beforeSave(Entity $entity, SaveOptions $options): void
    {
        $quoteId = $entity->get('quoteId');
        if ($quoteId) {
            $quote = $this->em->getEntityById('FusanheQuote', (string) $quoteId);
            if ($quote && in_array($quote->get('status'), self::FROZEN, true)) {
                throw new Conflict('The quote snapshot is frozen; revise the quote to change lines.');
            }
        }
        $quantity = (string) $entity->get('quantity');
        $unitPrice = (string) $entity->get('unitPrice');
        if (is_numeric($quantity) && is_numeric($unitPrice) && $quantity >= 0 && $unitPrice >= 0) {
            // Single rounding point, per contract: decimal half-up at 2 decimals.
            // bcadd at scale 2 of (product + 0.005) implements half-up for positives.
            $product = bcmul($quantity, $unitPrice, 6);
            $entity->set('amount', (float) bcadd($product, '0.005', 2));
        }
    }
}
