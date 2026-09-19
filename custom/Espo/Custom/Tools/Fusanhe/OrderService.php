<?php
namespace Espo\Custom\Tools\Fusanhe;

use Espo\Core\Exceptions\BadRequest;
use Espo\Core\Exceptions\Conflict;
use Espo\Core\Exceptions\NotFound;
use Espo\Entities\User;
use Espo\ORM\Entity;
use Espo\ORM\EntityManager;
use stdClass;

/**
 * Lightweight sales orders built from ACCEPTED quotes only. The order stores
 * a frozen snapshot of the quote's commercial terms and lines; shipments
 * validate quantities against order lines (no over-shipment, unit must
 * match). No MRP, no production scheduling, no stock ledger, no ERP.
 */
final class OrderService
{
    public function __construct(private EntityManager $em) {}

    public function createFromQuote(string $quoteId, User $user, stdClass $input): array
    {
        $quote = $this->em->getEntityById('FusanheQuote', $quoteId);
        if (!$quote) throw new NotFound('FusanheQuote not found.');
        if ($quote->get('status') !== 'accepted') {
            throw new Conflict('Orders can only be created from customer-accepted quotes.');
        }
        $customerRequiredDate = trim((string) ($input->customerRequiredDate ?? ''));
        if ($customerRequiredDate === '') throw new BadRequest('customerRequiredDate is required.');
        $name = trim((string) ($input->name ?? '')) ?: ('订单 ' . (string) $quote->get('number'));

        InternalWrite::wrap(function () use ($input, $quote, $name, $customerRequiredDate, &$order, &$items) {
            $order = $this->em->getNewEntity('FusanheSalesOrder');
            $order->set([
                'name' => $name,
                'quoteId' => $quote->getId(),
                'accountId' => $quote->get('accountId'),
                'contactId' => $quote->get('contactId'),
                'currency' => $quote->get('currency'),
                'tradeTerm' => $quote->get('tradeTerm'),
                'tradeTermPlace' => $quote->get('tradeTermPlace'),
                'tradeTermVersion' => $quote->get('tradeTermVersion'),
                'paymentTerms' => $quote->get('paymentTerms'),
                'leadTimeText' => $quote->get('leadTimeText'),
                'exchangeRate' => $quote->get('exchangeRate'),
                'exchangeRateDate' => $quote->get('exchangeRateDate'),
                'exchangeRateSource' => $quote->get('exchangeRateSource'),
                'quoteAcceptedAt' => $quote->get('acceptedAt'),
                'quoteAcceptedByRef' => $quote->get('acceptedByRef'),
                'customerRequiredDate' => $customerRequiredDate,
                'notesInternal' => $input->notesInternal ?? null,
                'assignedUserId' => $quote->get('assignedUserId'),
            ]);
            $this->em->saveEntity($order);
            $items = $this->em->getRDBRepository('FusanheQuoteItem')
                ->where(['quoteId' => $quote->getId()])->order('position', 'ASC')->find();
            foreach ($items as $item) {
                $line = $this->em->getNewEntity('FusanheOrderLine');
                $line->set([
                    'name' => $item->get('name'),
                    'orderId' => $order->getId(),
                    'position' => $item->get('position'),
                    'productId' => $item->get('productId'),
                    'productSpecId' => $item->get('productSpecId'),
                    'description' => $item->get('description'),
                    'quantity' => $item->get('quantity'),
                    'unit' => $item->get('unit'),
                    'unitPrice' => $item->get('unitPrice'),
                    'amount' => $item->get('amount'),
                    'packingSpec' => $item->get('packingSpec'),
                ]);
                $this->em->saveEntity($line);
            }
        });
        $this->audit('order.created', $user, $order, ['quoteId' => $quote->getId()]);
        return ['id' => $order->getId(), 'number' => $order->get('number'), 'lines' => count($items)];
    }

    public function transition(string $action, string $id, User $user, stdClass $input): array
    {
        $order = $this->em->getEntityById('FusanheSalesOrder', $id);
        if (!$order) throw new NotFound('FusanheSalesOrder not found.');
        $status = (string) $order->get('status');
        switch ($action) {
            case 'confirm':
                if ($status !== 'draft') throw new Conflict('Only draft orders can be confirmed.');
                $internalDate = trim((string) ($input->internalConfirmedDate ?? ''));
                if ($internalDate === '') throw new BadRequest('internalConfirmedDate is required to confirm an order.');
                $order->set(['status' => 'confirmed', 'internalConfirmedDate' => $internalDate]);
                break;
            case 'cancel':
                if (!in_array($status, ['draft', 'confirmed'], true)) {
                    throw new Conflict('Only draft or confirmed orders can be cancelled.');
                }
                $reason = trim((string) ($input->reason ?? ''));
                if ($reason === '') throw new BadRequest('reason is required to cancel an order.');
                $order->set(['status' => 'cancelled', 'cancelReason' => $reason]);
                break;
            case 'complete':
                if ($status !== 'confirmed') throw new Conflict('Only confirmed orders can be completed.');
                $openShipments = $this->em->getRDBRepository('FusanheOrderShipment')
                    ->where(['orderId' => $id, 'status' => ['planned', 'shipped']])->count();
                if ($openShipments > 0) {
                    throw new Conflict('Shipments are still planned or in transit; settle them before completing.');
                }
                $order->set('status', 'completed');
                break;
            default:
                throw new BadRequest('Unknown order action.');
        }
        InternalWrite::flag();
        $this->em->saveEntity($order);
        InternalWrite::clear();
        $this->audit('order.' . $action, $user, $order);
        return ['id' => $order->getId(), 'status' => $order->get('status')];
    }

    public function shipmentTransition(string $action, string $id, User $user, stdClass $input): array
    {
        $shipment = $this->em->getEntityById('FusanheOrderShipment', $id);
        if (!$shipment) throw new NotFound('FusanheOrderShipment not found.');
        $status = (string) $shipment->get('status');
        switch ($action) {
            case 'ship':
                if ($status !== 'planned') throw new Conflict('Only planned shipments can be marked shipped.');
                $shipment->set(['status' => 'shipped', 'actualShipDate' => (string) ($input->actualShipDate ?? gmdate('Y-m-d'))]);
                break;
            case 'arrive':
                if ($status !== 'shipped') throw new Conflict('Only shipped shipments can be marked arrived.');
                $shipment->set(['status' => 'arrived', 'actualArrivalDate' => (string) ($input->actualArrivalDate ?? gmdate('Y-m-d'))]);
                break;
            case 'cancel':
                if ($status !== 'planned') throw new Conflict('Only planned shipments can be cancelled.');
                $shipment->set('status', 'cancelled');
                break;
            default:
                throw new BadRequest('Unknown shipment action.');
        }
        InternalWrite::flag();
        $this->em->saveEntity($shipment);
        InternalWrite::clear();
        $this->audit('shipment.' . $action, $user, $shipment);
        return ['id' => $shipment->getId(), 'status' => $shipment->get('status')];
    }

    /** Batch traceability: batchCode -> shipment items -> shipments -> orders. */
    public function byBatch(string $batch): array
    {
        $batch = trim($batch);
        if ($batch === '') throw new BadRequest('batch is required.');
        $items = $this->em->getRDBRepository('FusanheShipmentItem')
            ->where(['batchCode' => $batch])->find();
        $result = [];
        foreach ($items as $item) {
            $shipment = $this->em->getEntityById('FusanheOrderShipment', (string) $item->get('shipmentId'));
            $order = $shipment ? $this->em->getEntityById('FusanheSalesOrder', (string) $shipment->get('orderId')) : null;
            $result[] = [
                'batchCode' => $batch,
                'quantity' => $item->get('quantity'),
                'unit' => $item->get('unit'),
                'orderLineId' => $item->get('orderLineId'),
                'shipmentId' => $item->get('shipmentId'),
                'shipmentStatus' => $shipment ? $shipment->get('status') : null,
                'orderId' => $order?->getId(),
                'orderNumber' => $order?->get('number'),
                'accountId' => $order?->get('accountId'),
            ];
        }
        return ['batch' => $batch, 'total' => count($result), 'list' => $result];
    }

    private function audit(string $event, User $user, Entity $entity, array $extra = []): void
    {
        $a = $this->em->getNewEntity('AutomationAudit');
        $a->set([
            'name' => $event . ' ' . date('H:i:s'),
            'eventType' => $event,
            'actorType' => 'user',
            'actorId' => $user->getId(),
            'entityType' => $entity->getEntityType(),
            'entityId' => $entity->getId(),
            'result' => 'success',
            'details' => $extra + ['status' => $entity->get('status')],
        ]);
        $this->em->saveEntity($a);
    }
}
