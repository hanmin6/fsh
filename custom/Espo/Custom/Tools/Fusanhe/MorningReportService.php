<?php
namespace Espo\Custom\Tools\Fusanhe;
use Espo\ORM\EntityManager;
use DateTimeImmutable;
use DateTimeZone;

final class MorningReportService
{
    public function __construct(private EntityManager $em, private MorningReportStore $store) {}
    private function rows(string $type, array $where = []): array
    {
        $out = [];
        foreach ($this->em->getRDBRepository($type)->where($where)->find() as $entity) {
            $row = (array) $entity->getValueMap(); $row['id'] = $entity->getId();
            if ($type === 'Lead') foreach (['emailAddress','phoneNumber'] as $field) $row[$field] = $entity->get($field);
            $out[] = $row;
        }
        return $out;
    }
    public function generate(string $date, ?DateTimeImmutable $now = null): array
    {
        $now ??= new DateTimeImmutable('now', new DateTimeZone('UTC'));
        $b = MorningReport::bounds($date);
        $cutoff = min($b['nightEnd'], $now->setTimezone(new DateTimeZone('UTC'))->format('Y-m-d H:i:s'));
        $conversations = $this->rows('ExternalConversation', ['lastInboundAt>=' => $b['dayStart'], 'lastInboundAt<' => $cutoff]);
        $newLeads = $this->rows('Lead', ['createdAt>=' => $b['dayStart'], 'createdAt<' => min($b['dayEnd'], $cutoff)]);
        $leadIds = array_values(array_filter(array_unique(array_column($conversations, 'leadId'))));
        $related = $leadIds ? $this->rows('Lead', ['id' => $leadIds]) : [];
        $tasks = $this->rows('OutboundTask', ['triggerType' => 'scheduledReception', 'executionMode' => 'real',
            'OR' => [['completedAt>=' => $b['nightStart'], 'completedAt<' => $cutoff], ['modifiedAt>=' => $b['nightStart'], 'modifiedAt<' => $cutoff]]]);
        // Include task conversations even if their last inbound has moved outside the window.
        $convIds = array_values(array_filter(array_unique(array_column($tasks, 'conversationId'))));
        if ($convIds) {
            $map = []; foreach (array_merge($conversations, $this->rows('ExternalConversation', ['id' => $convIds])) as $c) $map[$c['id']] = $c;
            $conversations = array_values($map);
            $leadIds = array_values(array_filter(array_unique(array_column($conversations, 'leadId'))));
            if ($leadIds) $related = $this->rows('Lead', ['id' => $leadIds]);
        }
        $inbounds = $this->rows('ExternalMessage', ['direction' => 'inbound', 'sentAt>=' => $b['dayStart'], 'sentAt<' => $cutoff, 'createdAt<' => $cutoff]);
        $asOf = new DateTimeImmutable($cutoff, new DateTimeZone('UTC'));
        $business = [];
        try {
            $business['acquisition'] = MorningReportBusiness::acquisition($this->rows('Lead',
                ['fusanheSourceSystem' => ['Muse','Xpoz','OpenOutreach'], 'createdAt<' => $cutoff]), $asOf);
        } catch (\Throwable $e) { $business['acquisition'] = ['available' => false]; }
        try {
            $runs = new AcquisitionRunStore();
            $runDate = (new DateTimeImmutable($date, new DateTimeZone('Asia/Shanghai')))->modify('-1 day')->format('Y-m-d');
            $run = $runs->read($runDate);
            $ids = $run['createdLeadIds'] ?? [];
            $business['acquisitionRun'] = AcquisitionRunStore::summary($date, $runs->settings(), $run, min($asOf, $now),
                $ids ? $this->rows('Lead', ['id' => $ids, 'createdAt<' => $cutoff]) : []);
        } catch (\Throwable $e) { $business['acquisitionRun'] = ['available' => false, 'warnings' => ['获客运行记录读取失败，请检查 CRM']]; }
        try {
            $settings = SalesStore::read();
            $mailbox = $this->em->getEntityById('EmailAccount', (string) $settings['emailAccountId']);
            $settings['smtpReady'] = $mailbox?->get('status') === 'Active' && $mailbox?->get('useSmtp');
            $submitted = $this->rows('ExternalMessage', ['direction' => 'outbound', 'automationKind' => 'aiSales',
                'sentAt>=' => $b['dayStart'], 'sentAt<' => $b['dayEnd'], 'createdAt<' => $cutoff]);
            $business['mail'] = MorningReportBusiness::mail($this->rows('FusanheSalesPlan', ['createdAt<' => $cutoff]), $submitted, $settings, $asOf);
        } catch (\Throwable $e) { $business['mail'] = ['available' => false]; }
        // Older imported emails can lack salesKind. Read the native sender/subject for classification.
        foreach ($inbounds as &$message) {
            $raw = (array) ($message['rawPayload'] ?? []);
            if (empty($raw['nativeEmailId'])) continue;
            $email = $this->em->getEntityById('Email', (string) $raw['nativeEmailId']);
            if ($email) { $message['morningSender'] = $email->get('fromAddress'); $message['morningSubject'] = $email->get('subject'); }
        }
        unset($message);
        $report = MorningReport::build($date, array_merge($newLeads, $related), $tasks, $conversations, $inbounds,
            $this->rows('ExternalChannel'), ReceptionSettings::read(), $now, $business);
        $report['deliveries'] = []; return $report;
    }
    public function view(string $date, bool $manage): array
    {
        $report = $this->store->read($date);
        if (!$report) return ['report' => null, 'date' => $date];
        if (!$manage) unset($report['deliveries']);
        return ['report' => $report, 'date' => $date];
    }
    public function overview(): array
    {
        $settings = $this->store->settings(); $dates = $this->store->dates();
        return ['settings' => $settings, 'dates' => $dates, 'report' => $dates ? $this->store->read($dates[0]) : null];
    }
    public function tick(?DateTimeImmutable $now = null, ?WeChatAccounts $accounts = null): array
    {
        $now ??= new DateTimeImmutable('now', new DateTimeZone('UTC'));
        $local = $now->setTimezone(new DateTimeZone('Asia/Shanghai')); $date = $local->format('Y-m-d');
        // Minute scheduler, bounded catch-up. Never push a late report in the afternoon.
        if ($local->format('H:i') < '09:00' || $local->format('H:i') >= '09:15') return ['due' => false];
        return $this->store->exclusive(function () use ($now, $date, $accounts) {
            $settings = $this->store->settings();
            if (!$settings['enabled'] || !$settings['firstDate'] || $date < $settings['firstDate']) return ['due' => false];
            $accounts ??= new WeChatAccounts(new WeChatApi());
            $report = $this->store->read($date);
            if (!$report) {
                // Failure to query any data aborts generation; missing data never becomes zero.
                $report = $this->generate($date, $now);
                foreach ($accounts->listing()['accounts'] as $a) if ($a['status'] === 'bound' && $a['enabled']) $report['deliveries'][$a['id']] = ['name' => $a['name'], 'status' => 'pending'];
                $this->store->save($report);
            }
            foreach ($report['deliveries'] as $id => $delivery) {
                if ($delivery['status'] !== 'pending') {
                    if ($delivery['status'] === 'preparing') {
                        $report['deliveries'][$id]['status'] = 'uncertain'; $report['deliveries'][$id]['error'] = 'report_uncertain'; $this->store->save($report);
                    }
                    continue;
                }
                // Persist a claim before calling the account sender, protecting crash recovery.
                $report['deliveries'][$id]['status'] = 'preparing'; $this->store->save($report);
                try { $result = $accounts->sendReport($id, 'morning-' . $date, $report['text']); }
                catch (\Throwable $e) { $result = ['status' => $e instanceof \InvalidArgumentException ? 'skipped' : 'uncertain', 'error' => $e instanceof \InvalidArgumentException ? 'account_unavailable' : 'report_uncertain']; }
                if ($result['status'] === 'preparing') $result['status'] = 'uncertain';
                $report['deliveries'][$id] = ['name' => $delivery['name']] + $result;
                unset($report['deliveries'][$id]['clientId']); $this->store->save($report);
            }
            return ['due' => true, 'date' => $date, 'deliveries' => array_count_values(array_column($report['deliveries'], 'status'))];
        }, false);
    }
}
