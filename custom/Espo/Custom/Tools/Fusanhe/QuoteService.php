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
 * Quote workflow: draft -> inReview -> approved -> accepted, with
 * copy-revision versioning. Accepted quotes are frozen snapshots; revisions
 * create NEW quotes in the same version chain. No sending, no pricing
 * promises, no payment integration. All amounts live in ONE currency per
 * quote; cross-currency math is never done automatically.
 */
final class QuoteService
{
    private const IMMUTABLE_AFTER_ACCEPT = [
        'name', 'currency', 'validUntil', 'tradeTerm', 'tradeTermPlace', 'tradeTermVersion',
        'paymentTerms', 'leadTimeText', 'exchangeRate', 'exchangeRateDate', 'exchangeRateSource',
        'accountId', 'contactId', 'inquiryId', 'notesInternal', 'acceptedAt', 'acceptedByRef',
    ];

    public function __construct(private EntityManager $em) {}

    public function approve(string $id, User $user): array
    {
        $quote = $this->requireEntity($id);
        if ($quote->get('status') !== 'inReview') {
            throw new Conflict('Only quotes in internal review can be approved.');
        }
        if ($this->missingItems($quote)) {
            throw new Conflict('Quote has no line items; add at least one line before approval.');
        }
        $quote->set(['status' => 'approved', 'approvedById' => $user->getId(), 'approvedAt' => gmdate('Y-m-d H:i:s')]);
        InternalWrite::wrap(function () use ($quote) {
            $this->em->saveEntity($quote);
        });
        $this->audit('quote.approved', $user, $quote);
        return ['id' => $quote->getId(), 'status' => 'approved'];
    }

    public function submit(string $id, User $user): array
    {
        $quote = $this->requireEntity($id);
        if ($quote->get('status') !== 'draft') {
            throw new Conflict('Only draft quotes can be submitted for review.');
        }
        if ($this->missingItems($quote)) {
            throw new Conflict('Quote has no line items; add at least one line before submitting.');
        }
        $quote->set('status', 'inReview');
        InternalWrite::wrap(function () use ($quote) {
            $this->em->saveEntity($quote);
        });
        $this->audit('quote.submitted', $user, $quote);
        return ['id' => $quote->getId(), 'status' => 'inReview'];
    }

    public function reject(string $id, User $user, string $reason): array
    {
        $quote = $this->requireEntity($id);
        if (!in_array($quote->get('status'), ['draft', 'inReview', 'approved'], true)) {
            throw new Conflict('Only active quotes can be rejected.');
        }
        $quote->set(['status' => 'rejected']);
        $quote->set('description', ((string) ($quote->get('description') ?: '') . "\n[拒绝原因 " . gmdate('Y-m-d') . '] ' . $reason));
        InternalWrite::wrap(function () use ($quote) {
            $this->em->saveEntity($quote);
        });
        $this->audit('quote.rejected', $user, $quote, ['reason' => $reason]);
        return ['id' => $quote->getId(), 'status' => 'rejected'];
    }

    public function accept(string $id, User $user, stdClass $input): array
    {
        $quote = $this->requireEntity($id);
        if ($quote->get('status') !== 'approved') {
            throw new Conflict('Only approved quotes can record customer acceptance.');
        }
        $acceptedByRef = trim((string) ($input->acceptedByRef ?? ''));
        if ($acceptedByRef === '') throw new BadRequest('acceptedByRef (customer acceptance record) is required.');
        $quote->set([
            'status' => 'accepted',
            'acceptedAt' => (string) ($input->acceptedAt ?? gmdate('Y-m-d')),
            'acceptedByRef' => $acceptedByRef,
        ]);
        InternalWrite::wrap(function () use ($quote) {
            $this->em->saveEntity($quote);
        });
        // The inquiry, if linked, is now quoted.
        if ($quote->get('inquiryId')) {
            $inquiry = $this->em->getEntityById('FusanheInquiry', (string) $quote->get('inquiryId'));
            if ($inquiry && $inquiry->get('status') === 'open') {
                $inquiry->set('status', 'quoted');
                $this->em->saveEntity($inquiry);
            }
        }
        $this->audit('quote.accepted', $user, $quote, ['acceptedByRef' => $acceptedByRef]);
        return ['id' => $quote->getId(), 'status' => 'accepted'];
    }

    public function copyRevision(string $id, User $user, ?string $note): array
    {
        $source = $this->requireEntity($id);
        if (in_array($source->get('status'), ['superseded', 'rejected'], true)) {
            throw new Conflict('Superseded or rejected quotes cannot be revised.');
        }
        $rootId = (string) ($source->get('rootId') ?: $source->getId());
        $maxVersion = 1;
        foreach ($this->em->getRDBRepository('FusanheQuote')->where(['rootId' => $rootId])->find() as $sibling) {
            $maxVersion = max($maxVersion, (int) $sibling->get('versionNo'));
        }
        // Accepted versions stay as immutable snapshots, never marked superseded.
        if (!in_array($source->get('status'), ['accepted'], true)) {
            $source->set('status', 'superseded');
            InternalWrite::wrap(function () use ($source) {
                $this->em->saveEntity($source);
            });
        }
        $copy = $this->em->getNewEntity('FusanheQuote');
        $copy->set([
            'name' => (string) $source->get('name'),
            'status' => 'draft',
            'versionNo' => $maxVersion + 1,
            'rootId' => $rootId,
            'revisionOfId' => $source->getId(),
            'accountId' => $source->get('accountId'),
            'contactId' => $source->get('contactId'),
            'inquiryId' => $source->get('inquiryId'),
            'conversationId' => $source->get('conversationId'),
            'sampleId' => $source->get('sampleId'),
            'currency' => $source->get('currency'),
            'validUntil' => $source->get('validUntil'),
            'tradeTerm' => $source->get('tradeTerm'),
            'tradeTermPlace' => $source->get('tradeTermPlace'),
            'tradeTermVersion' => $source->get('tradeTermVersion'),
            'paymentTerms' => $source->get('paymentTerms'),
            'leadTimeText' => $source->get('leadTimeText'),
            'exchangeRate' => $source->get('exchangeRate'),
            'exchangeRateDate' => $source->get('exchangeRateDate'),
            'exchangeRateSource' => $source->get('exchangeRateSource'),
            'notesInternal' => $note ?: $source->get('notesInternal'),
            'assignedUserId' => $source->get('assignedUserId'),
        ]);
        InternalWrite::wrap(function () use ($copy, $source) {
            $this->em->saveEntity($copy);
            foreach ($this->em->getRDBRepository('FusanheQuoteItem')->where(['quoteId' => $source->getId()])->order('position', 'ASC')->find() as $item) {
                $newItem = $this->em->getNewEntity('FusanheQuoteItem');
                $newItem->set([
                    'name' => $item->get('name'),
                    'quoteId' => $copy->getId(),
                    'position' => $item->get('position'),
                    'productId' => $item->get('productId'),
                    'productSpecId' => $item->get('productSpecId'),
                    'description' => $item->get('description'),
                    'quantity' => $item->get('quantity'),
                    'unit' => $item->get('unit'),
                    'unitPrice' => $item->get('unitPrice'),
                    'moq' => $item->get('moq'),
                    'packingSpec' => $item->get('packingSpec'),
                    'leadTimeText' => $item->get('leadTimeText'),
                    'remark' => $item->get('remark'),
                    'internalNote' => $item->get('internalNote'),
                ]);
                $this->em->saveEntity($newItem);
            }
        });
        $this->audit('quote.revised', $user, $copy, ['sourceId' => $source->getId(), 'versionNo' => $copy->get('versionNo')]);
        return ['id' => $copy->getId(), 'versionNo' => (int) $copy->get('versionNo'), 'sourceId' => $source->getId()];
    }

    /** Missing-information checklist for an inquiry (read-only). */
    public function inquiryMissing(string $id): array
    {
        $inquiry = $this->em->getEntityById('FusanheInquiry', $id);
        if (!$inquiry) throw new NotFound('FusanheInquiry not found.');
        $missing = [];
        foreach ([
            '产品' => $inquiry->get('productId'),
            '数量与单位' => ($inquiry->get('quantity') && $inquiry->get('unit')),
            '目的港/地' => $inquiry->get('destination'),
            '交期要求' => $inquiry->get('deliveryWindow'),
            '包装要求' => $inquiry->get('packagingRequirement'),
            '所需证书' => $inquiry->get('certificatesNeeded'),
        ] as $label => $present) {
            if (!$present) $missing[] = $label;
        }
        return ['id' => $id, 'missing' => $missing, 'complete' => count($missing) === 0];
    }

    /**
     * Printable draft document (quotation or PI). Customer-safe: internal
     * notes never render. Always clearly marked as a DRAFT.
     */
    public function print(string $id, string $kind, User $user): array
    {
        if (!in_array($kind, ['quotation', 'pi'], true)) throw new BadRequest('kind must be quotation or pi.');
        $quote = $this->requireEntity($id);
        $items = $this->em->getRDBRepository('FusanheQuoteItem')
            ->where(['quoteId' => $id])->order('position', 'ASC')->find();
        $account = $this->em->getEntityById('Account', (string) $quote->get('accountId'));
        $total = 0.0;
        $rows = [];
        foreach ($items as $item) {
            // Use the stored, server-computed line amount; never re-derive it.
            $amount = round((float) $item->get('amount'), 2);
            $total += $amount;
            $rows[] = [
                'position' => $item->get('position'),
                'description' => $item->get('description') ?: $item->get('name') ?: (string) $item->get('productName'),
                'specVersion' => (string) $item->get('productSpecName'),
                'quantity' => (float) $item->get('quantity'),
                'unit' => (string) $item->get('unit'),
                'unitPrice' => (float) $item->get('unitPrice'),
                'amount' => $amount,
                'moq' => $item->get('moq'),
                'packingSpec' => $item->get('packingSpec'),
                'leadTimeText' => $item->get('leadTimeText'),
                'remark' => $item->get('remark'),
            ];
        }
        $total = round($total, 2);
        $this->audit('quote.printed', $user, $quote, ['kind' => $kind]);
        return [
            'kind' => $kind,
            'title' => $kind === 'pi' ? 'PROFORMA INVOICE (DRAFT 草稿)' : 'QUOTATION (DRAFT 草稿)',
            'number' => $quote->get('number'),
            'versionNo' => (int) $quote->get('versionNo'),
            'date' => gmdate('Y-m-d'),
            'status' => $quote->get('status'),
            'validUntil' => $quote->get('validUntil'),
            'seller' => ['name' => '福三和食品进出口有限公司', 'note' => '演示文档 - Demo document'],
            'buyer' => [
                'name' => $account ? (string) $account->get('name') : (string) $quote->get('accountName'),
                'attn' => (string) $quote->get('contactName'),
            ],
            'currency' => $quote->get('currency'),
            'tradeTerm' => $quote->get('tradeTerm'),
            'tradeTermPlace' => $quote->get('tradeTermPlace'),
            'tradeTermVersion' => $quote->get('tradeTermVersion'),
            'paymentTerms' => $quote->get('paymentTerms'),
            'leadTimeText' => $quote->get('leadTimeText'),
            'items' => $rows,
            'totalAmount' => $total,
            'draft' => true,
        ];
    }

    private function missingItems(Entity $quote): bool
    {
        return $this->em->getRDBRepository('FusanheQuoteItem')->where(['quoteId' => $quote->getId()])->count() === 0;
    }

    private function requireEntity(string $id): Entity
    {
        $entity = $this->em->getEntityById('FusanheQuote', $id);
        if (!$entity) throw new NotFound('FusanheQuote not found.');
        return $entity;
    }

    private function audit(string $event, User $user, Entity $quote, array $extra = []): void
    {
        $a = $this->em->getNewEntity('AutomationAudit');
        $a->set([
            'name' => $event . ' ' . date('H:i:s'),
            'eventType' => $event,
            'actorType' => 'user',
            'actorId' => $user->getId(),
            'entityType' => 'FusanheQuote',
            'entityId' => $quote->getId(),
            'result' => 'success',
            'details' => $extra + ['status' => $quote->get('status')],
        ]);
        $this->em->saveEntity($a);
    }
}
