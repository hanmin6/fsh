<?php
require ($argv[1] ?? dirname(__DIR__) . '/custom/Espo/Custom/Tools/Fusanhe') . '/CardProgress.php';
use Espo\Custom\Tools\Fusanhe\CardProgress;

function check(bool $condition, string $name): void {
    if (!$condition) throw new RuntimeException($name);
    echo "PASS $name\n";
}
$now = new DateTimeImmutable('2026-10-02T10:00:00Z');
$base = ['source' => 'Muse', 'direction' => 'outbound', 'deliveryStatus' => 'sent',
    'sentAt' => '2026-10-02 01:00:00', 'customerKey' => 'Lead:customer-1'];
$events = [$base, array_replace($base, ['deliveryStatus' => 'delivered'])];
foreach (['queued', 'sending', 'failed', 'mockSent', 'received'] as $status) {
    $events[] = array_replace($base, ['customerKey' => 'bad:' . $status, 'deliveryStatus' => $status]);
}
foreach ([['source'=>'Alibaba'], ['direction'=>'inbound'], ['sentAt'=>'invalid'],
    ['customerKey'=>null], ['sentAt'=>'2026-10-02 12:00:00']] as $change) {
    $events[] = array_replace($base, $change);
}
$result = CardProgress::summarize($events, $now);
check($result['todayCompleted'] === 1 && $result['remaining'] === 14, 'deduplicates customers and excludes unconfirmed or future deliveries');
[$start, $end] = CardProgress::bounds($now);
check($start->format('c') === '2026-10-01T16:00:00+00:00' && $end->format('c') === '2026-10-02T16:00:00+00:00', 'Shanghai daily boundaries in UTC');
$result = CardProgress::summarize([
    array_replace($base, ['sentAt'=>'2026-10-01 15:59:59', 'customerKey'=>'previous']),
    array_replace($base, ['sentAt'=>'2026-10-01 16:00:00', 'customerKey'=>'today']),
], $now);
check($result['todayCompleted'] === 1, 'includes midnight and excludes previous calendar day');
check(CardProgress::summarize([$base], new DateTimeImmutable('2026-10-02T16:00:01Z'))['todayCompleted'] === 0, 'resets count after Shanghai midnight');
$events = [];
for ($i=0; $i<16; $i++) $events[] = array_replace($base, ['customerKey'=>'Lead:'.$i]);
$result = CardProgress::summarize($events, $now);
check($result['todayCompleted'] === 16 && $result['remaining'] === 0 && $result['dailyTarget'] === 15, 'reports real counts above target without negative remainder');
$result = CardProgress::summarize([], $now);
check($result['todayCompleted'] === 0 && $result['lastSentAt'] === null, 'empty records have zero progress and no invented success timestamp');
