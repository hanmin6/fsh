<?php
namespace Espo\Custom\Tools\Fusanhe;
use DateTimeImmutable;
use DateTimeZone;

/** Facts and fixed evidence-based recommendations; no invented counts or business promises. */
final class MorningReport
{
    public static function bounds(string $date): array
    {
        if (!MorningReportStore::validDate($date)) throw new \InvalidArgumentException('invalid_report_date');
        $local = new DateTimeImmutable($date, new DateTimeZone('Asia/Shanghai'));
        $utc = new DateTimeZone('UTC');
        return ['dayStart' => $local->modify('-1 day')->setTimezone($utc)->format('Y-m-d H:i:s'),
            'dayEnd' => $local->setTimezone($utc)->format('Y-m-d H:i:s'),
            'nightStart' => $local->modify('-1 day')->setTime(19, 0)->setTimezone($utc)->format('Y-m-d H:i:s'),
            'nightEnd' => $local->setTime(9, 0)->setTimezone($utc)->format('Y-m-d H:i:s')];
    }
    public static function contact(array $lead): bool
    {
        $email = trim((string) ($lead['emailAddress'] ?? ''));
        $phone = preg_replace('/[^0-9]/', '', (string) ($lead['phoneNumber'] ?? ''));
        return (bool) filter_var($email, FILTER_VALIDATE_EMAIL) || (strlen($phone) >= 7 && strlen($phone) <= 15 && !preg_match('/^(\d)\1+$/', $phone));
    }
    private static function label(string $name): string
    {
        return mb_substr(trim(preg_replace('/[\x00-\x1f\x7f]/u', ' ', $name)), 0, 60) ?: '未命名客户';
    }
    private static function customer(array $c): string
    {
        foreach (['lead', 'contact', 'account', 'identity'] as $type) if (!empty($c[$type . 'Id'])) return $type . ':' . $c[$type . 'Id'];
        return 'conversation:' . ($c['id'] ?? '');
    }
    public static function build(string $date, array $leads, array $tasks, array $conversations, array $inbounds, array $channels, array $reception, DateTimeImmutable $now, array $business = []): array
    {
        $bounds = self::bounds($date); $cutoff = min($bounds['nightEnd'], $now->setTimezone(new DateTimeZone('UTC'))->format('Y-m-d H:i:s'));
        $new = []; $leadMap = []; $high = 0; $contacts = 0;
        foreach ($leads as $lead) {
            $id = $lead['id'] ?? ''; if (!$id) continue; $leadMap[$id] = $lead;
            $at = $lead['createdAt'] ?? '';
            if ($at < $bounds['dayStart'] || $at >= min($bounds['dayEnd'], $cutoff) || isset($new[$id])) continue;
            $new[$id] = $lead;
            if (in_array(AcquisitionRouting::effectiveRating($lead), ['S', 'A'], true)) $high++;
            if (self::contact($lead)) $contacts++;
        }
        $convMap = []; foreach ($conversations as $c) $convMap[$c['id']] = $c;
        $replied = []; $handoff = []; $replyCount = 0; $failed = 0; $uncertain = 0; $seen = [];
        foreach ($tasks as $task) {
            if (($task['triggerType'] ?? '') !== 'scheduledReception' || ($task['executionMode'] ?? '') !== 'real' || empty($task['id']) || isset($seen[$task['id']])) continue;
            $seen[$task['id']] = true;
            $at = $task['completedAt'] ?? $task['modifiedAt'] ?? $task['createdAt'] ?? '';
            if (!$at || $at < $bounds['nightStart'] || $at >= $cutoff) continue;
            $status = $task['status'] ?? '';
            if ($status === 'failed') { $failed++; continue; }
            if ($status === 'sending') { $uncertain++; continue; }
            if ($status !== 'sent' || empty($task['completedAt'])) continue;
            $replyCount++; $c = $convMap[$task['conversationId'] ?? ''] ?? ['id' => $task['conversationId'] ?? $task['id']];
            $key = self::customer($c); $replied[$key] = true;
            $lead = $leadMap[$c['leadId'] ?? ''] ?? [];
            if (($c['status'] ?? '') !== 'closed' && (in_array(AcquisitionRouting::effectiveRating($lead), ['S','A'], true) || ($c['controlMode'] ?? '') === 'human')) $handoff[$key] = true;
        }
        $channelMap = []; foreach ($channels as $ch) $channelMap[$ch['id'] ?? ''] = $ch;
        $latest = [];
        foreach ($inbounds as $m) {
            $cid = $m['conversationId'] ?? ''; $at = $m['sentAt'] ?? '';
            if (($m['direction'] ?? '') !== 'inbound' || !$cid || !$at || $at < $bounds['dayStart'] || $at >= $cutoff || ($m['createdAt'] ?? $at) >= $cutoff) continue;
            $raw = (array) ($m['rawPayload'] ?? []);
            if (isset($raw['salesKind']) && $raw['salesKind'] !== 'customer') continue;
            $c = $convMap[$cid] ?? [];
            if (($channelMap[$c['channelId'] ?? '']['type'] ?? '') === 'Email' &&
                SalesPolicy::classify((string) ($m['morningSender'] ?? $raw['senderAddress'] ?? $m['senderExternalId'] ?? ''),
                    (string) ($m['morningSubject'] ?? $c['subject'] ?? $c['name'] ?? ''), (string) ($m['body'] ?? ''),
                    ['autoSubmitted' => $raw['autoSubmitted'] ?? '']) !== 'customer') continue;
            if (!isset($latest[$cid]) || $at > ($latest[$cid]['sentAt'] ?? '')) $latest[$cid] = $m;
        }
        $candidates = [];
        $topics = ['price_question' => ['明确询问报价', '建议负责人上午核对规格与数量后联系'],
            'delivery_question' => ['询问交付时间', '需要人工核实交期后回复'],
            'sample_question' => ['提出样品需求', '建议确认样品规格、数量及收件信息'],
            'certificate_question' => ['询问产品认证', '建议核实适用证书后回复'],
            'specification_question' => ['询问产品规格或包装', '建议核实需求并提供对应资料']];
        foreach ($conversations as $c) {
            if (($c['status'] ?? '') === 'closed') continue;
            $lead = $leadMap[$c['leadId'] ?? ''] ?? [];
            if ($lead && AcquisitionRouting::route($lead) === 'blocked') continue;
            $m = $latest[$c['id']] ?? null;
            if (!$m) continue;
            $signals = HistorySignals::signals((string) ($m['body'] ?? '')); $reason = ''; $action = ''; $score = 50;
            foreach ($topics as $code => [$r, $a]) if (in_array($code, $signals, true)) { $reason = $r; $action = $a; $score = 10; break; }
            $rating = AcquisitionRouting::effectiveRating($lead);
            if (in_array($rating, ['S','A'], true)) {
                $score -= 5;
                if (!$reason) { $reason = $rating . ' 级客户有新消息'; $action = '建议负责人上午查看完整询盘并联系'; }
            }
            if (!$reason && empty($c['assignedUserId']) && self::contact($lead)) { $reason = '留有有效联系方式，尚未分配跟进人员'; $action = '建议上午分配负责人'; $score = 20; }
            if (!$reason && empty($c['lastOutboundAt'])) { $reason = '客户新消息尚无回复记录'; $action = '建议查看询盘并及时回复'; $score = 30; }
            if (!$reason) continue;
            // Suppress a topic already answered by a human after the latest inbound.
            if ($score === 10 && ($c['controlMode'] ?? '') !== 'human' && ($c['lastOutboundAt'] ?? '') > $m['sentAt'] && !isset($replied[self::customer($c)])) continue;
            $candidates[] = ['customerKey' => self::customer($c), 'name' => self::label((string) ($c['name'] ?? $lead['name'] ?? '')),
                'reason' => $reason, 'action' => $action, 'owner' => self::label((string) ($c['assignedUserName'] ?? '待分配')),
                'url' => 'https://crm.fsh.digital/?workspace=messages&record=' . rawurlencode($c['id']) . '#Home/workspace',
                'sourceMessageId' => $m['id'] ?? null, 'score' => $score, 'at' => $m['sentAt']];
        }
        foreach ($new as $lead) {
            if (AcquisitionRouting::route($lead) === 'blocked' || !empty($lead['assignedUserId']) || !self::contact($lead)) continue;
            $candidates[] = ['customerKey' => 'lead:' . $lead['id'], 'name' => self::label((string) ($lead['name'] ?? $lead['accountName'] ?? '')),
                'reason' => '新线索留有有效联系方式，尚未分配跟进人员', 'action' => '建议上午分配负责人', 'owner' => '待分配',
                'url' => 'https://crm.fsh.digital/#Lead/view/' . rawurlencode($lead['id']), 'score' => 20, 'at' => $lead['createdAt']];
        }
        usort($candidates, fn($a, $b) => ($a['score'] <=> $b['score']) ?: strcmp($b['at'], $a['at']) ?: strcmp($a['customerKey'], $b['customerKey']));
        $priorities = []; $selected = [];
        foreach ($candidates as $p) { if (isset($selected[$p['customerKey']])) continue; $selected[$p['customerKey']] = true; unset($p['score']); $priorities[] = $p; if (count($priorities) === 3) break; }
        $warnings = $business['acquisitionRun']['warnings'] ?? [];
        if ($failed) $warnings[] = "有 {$failed} 条夜间自动回复发送失败，待检查";
        if ($uncertain) $warnings[] = "有 {$uncertain} 条夜间自动回复发送结果待确认，请先核对平台记录";
        if (empty($reception['enabled'])) $warnings[] = '夜间自动接待当前未开启';
        foreach ($channels as $channel) {
            if (empty($channel['enabled']) || !in_array($channel['type'] ?? '', ['Alibaba', 'MadeInChina'], true)) continue;
            $last = $channel['lastSyncAt'] ?? '';
            $age = $last ? $now->getTimestamp() - (new DateTimeImmutable($last, new DateTimeZone('UTC')))->getTimestamp() : PHP_INT_MAX;
            if (($channel['connectionStatus'] ?? '') !== 'healthy' || $age > 1800) $warnings[] = self::label($channel['name'] ?? '采集渠道') . ' 同步异常或已超过 30 分钟未更新，统计可能不完整';
        }
        $month = (int) substr($date,5,2); $day = (int) substr($date,8,2);
        $text = "福三和晨报｜{$month} 月 {$day} 日\n\n昨晚自动回复了 " . count($replied) . " 位客户，共 {$replyCount} 条消息，其中 " . count($handoff) . " 位需要人工接手。\n昨天 CRM 共新增 " . count($new) . " 条线索，其中 S/A 级 {$high} 条；新线索中留有有效联系方式 {$contacts} 份。\n";
        $text .= MorningReportBusiness::text($business) . "\n今天优先关注：\n";
        foreach ($priorities as $i => $p) $text .= ['①','②','③'][$i] . ' ' . $p['name'] . '：' . $p['reason'] . '，' . $p['action'] . '。' . ($p['owner'] !== '待分配' ? '负责人：' . $p['owner'] . '。' : '') . "\n";
        if (!$priorities) $text .= "暂无符合优先关注条件的事项。\n";
        $text .= "\n运行提醒：" . ($warnings ? implode('；', array_slice($warnings,0,5)) . '。' : '未发现发送失败或渠道同步异常。') . "\n查看完整晨报 → https://crm.fsh.digital/?workspace=wechat&reportDate={$date}#Home/workspace";
        return ['date' => $date, 'timezone' => 'Asia/Shanghai', 'bounds' => $bounds, 'cutoff' => $cutoff,
            'metrics' => ['replyCustomers' => count($replied), 'replyMessages' => $replyCount, 'handoffCustomers' => count($handoff), 'newLeads' => count($new), 'highValueLeads' => $high, 'validContacts' => $contacts, 'failedReplies' => $failed, 'uncertainReplies' => $uncertain],
            'business' => $business, 'priorities' => $priorities, 'warnings' => $warnings, 'text' => $text, 'contentHash' => hash('sha256', $text),
            'generatedAt' => $now->setTimezone(new DateTimeZone('UTC'))->format('c')];
    }
}
