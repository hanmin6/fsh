<?php
namespace Espo\Custom\Tools\Fusanhe;
use DateTimeImmutable;
use DateTimeZone;

/** Read-only projections from AI acquisition and the existing sales executor. */
final class MorningReportBusiness
{
    public static function acquisition(iterable $leads, DateTimeImmutable $asOf): array
    {
        return ['available' => true] + CardProgress::summarize($leads, $asOf);
    }
    public static function mail(array $plans, array $messages, array $settings, DateTimeImmutable $asOf): array
    {
        $utc = $asOf->setTimezone(new DateTimeZone('UTC'))->format('Y-m-d H:i:s');
        [$dayStart, $dayEnd] = CardProgress::bounds($asOf);
        $nextMorning = $asOf->setTimezone(new DateTimeZone('Asia/Shanghai'))->setTime(9, 0)->modify('+1 day')->setTimezone(new DateTimeZone('UTC'))->format('Y-m-d H:i:s');
        $counts = array_fill_keys(['scheduled','wait_data','preview','sending','submitted','uncertain','human','stopped','failed','planning'], 0);
        $next = []; $seen = []; $blockedSchedules = 0; $window = 0;
        foreach ($plans as $row) {
            $id = (string) ($row['id'] ?? '');
            if ($id === '' || isset($seen[$id]) || ($row['createdAt'] ?? $utc) > $utc) continue;
            $seen[$id] = true; $status = $row['status'] ?? '';
            if (isset($counts[$status])) $counts[$status]++;
            if ($status !== 'scheduled') continue;
            $plan = (array) ($row['plan'] ?? []); $due = (string) ($row['dueAt'] ?? '');
            if ($due === '' || ($plan['action'] ?? '') !== 'send' || $due !== ($plan['dueUtc'] ?? '') ||
                empty($settings['activationEpoch']) || ($row['activationEpoch'] ?? null) !== $settings['activationEpoch'] ||
                !empty($plan['validUntilUtc']) && $plan['validUntilUtc'] < $utc) { $blockedSchedules++; continue; }
            try { $date = new DateTimeImmutable($due, new DateTimeZone('UTC')); }
            catch (\Throwable $e) { $blockedSchedules++; continue; }
            if ($due >= $utc && $due < $nextMorning) $window++;
            $zone = (string) ($plan['timezone'] ?? ''); $local = null;
            if (in_array($zone, DateTimeZone::listIdentifiers(), true)) $local = $date->setTimezone(new DateTimeZone($zone))->format('m月d日 H:i');
            $next[] = ['id' => $id, 'name' => mb_substr((string) ($row['name'] ?? '未命名客户'), 0, 80),
                'dueAt' => $due, 'beijingTime' => $date->setTimezone(new DateTimeZone('Asia/Shanghai'))->format('m月d日 H:i'),
                'customerLocalTime' => $local, 'timezone' => $zone, 'overdue' => $due < $utc,
                'url' => 'https://crm.fsh.digital/?workspace=sales#Home/workspace'];
        }
        usort($next, fn($a, $b) => strcmp($a['dueAt'], $b['dueAt']) ?: strcmp($a['id'], $b['id']));
        $submitted = []; $messageIds = [];
        foreach ($messages as $m) {
            $at = (string) ($m['sentAt'] ?? ''); $id = (string) ($m['id'] ?? '');
            if ($id === '' || isset($messageIds[$id]) || ($m['direction'] ?? '') !== 'outbound' ||
                ($m['automationKind'] ?? '') !== 'aiSales' || !in_array($m['deliveryStatus'] ?? '', ['sent','delivered'], true) ||
                $at < $dayStart->format('Y-m-d H:i:s') || $at >= $dayEnd->format('Y-m-d H:i:s') || ($m['createdAt'] ?? $at) > $utc) continue;
            $messageIds[$id] = true;
            $raw = (array) ($m['rawPayload'] ?? []);
            $submitted[(string) ($raw['nativeEmailId'] ?? $m['externalId'] ?? $id)] = true;
        }
        return ['available' => true, 'enabled' => (bool) ($settings['enabled'] ?? false), 'smtpReady' => (bool) ($settings['smtpReady'] ?? false),
            'counts' => $counts, 'validScheduled' => count($next), 'blockedSchedules' => $blockedSchedules,
            'untilNextMorning' => $window, 'yesterdaySubmitted' => count($submitted), 'next' => array_slice($next, 0, 3), 'checkedAt' => $utc];
    }
    public static function text(array $business): string
    {
        $a = $business['acquisition'] ?? [];
        $text = "\nAI 获客：";
        if (empty($a['available'])) $text .= "数据暂不可用，请查看 CRM 获客页面。\n";
        else {
            $text .= "昨天获得 {$a['yesterdayAcquired']} 条客资，累计入库 {$a['totalAcquired']} 条；昨日 S/A 级 {$a['yesterdayValueCounts']['high']} 条。\n";
            $text .= "客资跟进：人工 {$a['followUpCounts']['human']} 条，AI {$a['followUpCounts']['ai']} 条，待评级 {$a['followUpCounts']['pending_rating']} 条，禁止联系 {$a['followUpCounts']['blocked']} 条。\n";
        }
        if (isset($business['acquisitionRun'])) $text .= AcquisitionRunStore::text($business['acquisitionRun']);
        $m = $business['mail'] ?? []; $text .= "\n邮件安排：";
        if (empty($m['available'])) return $text . "计划读取失败，请查看 CRM 的 AI 客户跟进页面。\n";
        $state = !$m['enabled'] ? '自动邮件已暂停' : (!$m['smtpReady'] ? '邮件通道未就绪' : '自动邮件已开启');
        $text .= $state . "；已排期 {$m['validScheduled']} 封，待补资料 {$m['counts']['wait_data']} 位，待审核预览 {$m['counts']['preview']} 份。\n";
        if (!$m['next']) $text .= "暂无可执行的邮件发送时间。\n";
        foreach ($m['next'] as $p) {
            $text .= '• ' . $p['name'] . '：' . $p['beijingTime'] . '（北京时间）';
            if ($p['customerLocalTime']) $text .= '；客户当地 ' . $p['customerLocalTime'] . ' · ' . $p['timezone'];
            if ($p['overdue']) $text .= '，已过计划时间，需核对执行结果';
            $text .= "。\n";
        }
        $text .= "昨天 AI 邮件提交 {$m['yesterdaySubmitted']} 封；发送中 {$m['counts']['sending']} 封，结果待确认 {$m['counts']['uncertain']} 封，失败 {$m['counts']['failed']} 封。计划发送时间以执行前检查为准。\n";
        return $text;
    }
}
