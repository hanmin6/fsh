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
 * Sample workflow: requested -> preparing -> sent -> delivered ->
 * feedbackReceived -> closed, plus cancel (only before sending) and
 * exception/return records (only after sending). All transitions are
 * audited; generic CRUD cannot drive the status machine.
 */
final class SampleService
{
    private const NEXT = [
        'requested' => ['preparing', 'sent', 'cancelled'],
        'preparing' => ['sent', 'cancelled'],
        'sent' => ['delivered'],
        'delivered' => ['feedbackReceived', 'closed'],
        'feedbackReceived' => ['closed'],
        'closed' => [],
        'cancelled' => [],
    ];

    public function __construct(private EntityManager $em) {}

    public function transition(string $action, string $id, User $user, stdClass $input): array
    {
        $sample = $this->requireEntity($id);
        $status = (string) $sample->get('status');

        switch ($action) {
            case 'prepare':
                $this->assertTransition($sample, 'preparing');
                $sample->set('status', 'preparing');
                break;
            case 'send':
                $this->assertTransition($sample, 'sent');
                $trackingNo = trim((string) ($input->trackingNo ?? ''));
                if ($trackingNo === '') throw new BadRequest('trackingNo is required when sending a sample.');
                $sample->set([
                    'status' => 'sent',
                    'trackingNo' => $trackingNo,
                    'trackingCarrier' => trim((string) ($input->carrier ?? '')),
                    'sentAt' => (string) ($input->sentAt ?? gmdate('Y-m-d')),
                ]);
                break;
            case 'deliver':
                $this->assertTransition($sample, 'delivered');
                $sample->set([
                    'status' => 'delivered',
                    'deliveredAt' => (string) ($input->deliveredAt ?? gmdate('Y-m-d')),
                ]);
                break;
            case 'feedback':
                $this->assertTransition($sample, 'feedbackReceived');
                $feedback = trim((string) ($input->feedback ?? ''));
                if ($feedback === '') throw new BadRequest('feedback text is required.');
                $result = (string) ($input->feedbackResult ?? 'positive');
                if (!in_array($result, ['positive', 'mixed', 'negative'], true)) throw new BadRequest('feedbackResult must be positive, mixed or negative.');
                $sample->set([
                    'status' => 'feedbackReceived',
                    'feedback' => $feedback,
                    'feedbackResult' => $result,
                    'feedbackAt' => gmdate('Y-m-d H:i:s'),
                ]);
                break;
            case 'close':
                $this->assertTransition($sample, 'closed');
                $sample->set('status', 'closed');
                break;
            case 'cancel':
                if (!in_array($status, ['requested', 'preparing'], true)) {
                    throw new Conflict('Only samples not yet sent can be cancelled.');
                }
                $reason = trim((string) ($input->reason ?? ''));
                if ($reason === '') throw new BadRequest('reason is required to cancel a sample.');
                $sample->set(['status' => 'cancelled', 'cancelReason' => $reason]);
                break;
            case 'return':
                if (!in_array($status, ['sent', 'delivered'], true)) {
                    throw new Conflict('Only sent or delivered samples can record a return.');
                }
                $note = trim((string) ($input->note ?? ''));
                if ($note === '') throw new BadRequest('note is required for a return record.');
                $sample->set([
                    'returned' => true,
                    'returnedAt' => (string) ($input->returnedAt ?? gmdate('Y-m-d')),
                    'returnNote' => $note,
                ]);
                break;
            case 'exception':
                if (in_array($status, ['cancelled', 'closed'], true)) {
                    throw new Conflict('Cancelled or closed samples accept no new exception records.');
                }
                $note = trim((string) ($input->note ?? ''));
                if ($note === '') throw new BadRequest('note is required for an exception record.');
                $sample->set('exceptionNote', ((string) ($sample->get('exceptionNote') ?: '') . "\n[" . gmdate('Y-m-d') . '] ' . $note));
                break;
            default:
                throw new BadRequest('Unknown sample action.');
        }

        InternalWrite::wrap(function () use ($sample) {
            $this->em->saveEntity($sample);
        });
        $this->audit($action, $user, $sample);
        return ['id' => $sample->getId(), 'status' => $sample->get('status')];
    }

    public function createFollowUp(string $id, User $user, ?string $intent, ?string $note): array
    {
        $sample = $this->requireEntity($id);
        $intent = trim((string) $intent) ?: '样品跟进';
        $name = '跟进 · ' . $intent . ' · ' . (string) $sample->get('name');
        $existing = $this->em->getRDBRepository('Task')->where([
            'parentType' => 'FusanheSample',
            'parentId' => $id,
            'name' => $name,
            'status' => ['Not Started', 'Started'],
        ])->findOne();
        if ($existing) {
            return ['taskId' => $existing->getId(), 'deduplicated' => true];
        }
        $task = $this->em->getNewEntity('Task');
        $task->set([
            'name' => $name,
            'status' => 'Not Started',
            'priority' => 'Normal',
            'parentType' => 'FusanheSample',
            'parentId' => $id,
            'dateEnd' => (new \DateTimeImmutable('+3 days'))->format('Y-m-d') . ' 18:00:00',
            'description' => $note ?: ('样品「' . (string) $sample->get('name') . '」的人工跟进任务。'),
            'assignedUserId' => $sample->get('assignedUserId'),
        ]);
        $this->em->saveEntity($task);
        $this->audit('followup', $user, $sample, ['taskId' => $task->getId()]);
        return ['taskId' => $task->getId(), 'deduplicated' => false];
    }

    private function assertTransition(Entity $sample, string $target): void
    {
        $status = (string) $sample->get('status');
        if (!in_array($target, self::NEXT[$status] ?? [], true)) {
            throw new Conflict("Cannot move a {$status} sample to {$target}.");
        }
    }

    private function requireEntity(string $id): Entity
    {
        $entity = $this->em->getEntityById('FusanheSample', $id);
        if (!$entity) throw new NotFound('FusanheSample not found.');
        return $entity;
    }

    private function audit(string $action, User $user, Entity $sample, array $extra = []): void
    {
        $a = $this->em->getNewEntity('AutomationAudit');
        $a->set([
            'name' => 'sample.' . $action . ' ' . date('H:i:s'),
            'eventType' => 'sample.' . $action,
            'actorType' => 'user',
            'actorId' => $user->getId(),
            'entityType' => 'FusanheSample',
            'entityId' => $sample->getId(),
            'result' => 'success',
            'details' => $extra + ['status' => $sample->get('status')],
        ]);
        $this->em->saveEntity($a);
    }
}
