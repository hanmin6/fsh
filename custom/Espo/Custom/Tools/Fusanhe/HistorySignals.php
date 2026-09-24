<?php
namespace Espo\Custom\Tools\Fusanhe;

/** Only fixed vocabulary leaves this process. No free-text redaction heuristic. */
final class HistorySignals
{
    public const VERSION = 'history-signals-v1';
    private const TERMS = [
        'price_question' => '/\b(price|quotation|quote|pricing)\b|报价|价格/iu',
        'sample_question' => '/\bsamples?\b|样品|索样/iu',
        'specification_question' => '/\b(specification|ingredients?|packing|packaging)\b|规格|配料|包装/iu',
        'delivery_question' => '/\b(delivery|shipping|lead time)\b|交期|运输/iu',
        'certificate_question' => '/\b(certificat\w*|halal|haccp)\b|认证|证书/iu',
    ];

    public static function signals(string $body): array
    {
        $out = [];
        foreach (self::TERMS as $code => $pattern) if (preg_match($pattern, $body)) $out[] = $code;
        return $out;
    }

    public static function day(?string $now = null): string
    {
        return (new \DateTimeImmutable($now ?? 'now', new \DateTimeZone('UTC')))
            ->setTimezone(new \DateTimeZone('Asia/Shanghai'))->format('Y-m-d');
    }

    public static function suggestion(array $c, ?int $now = null): ?array
    {
        if (($c['status'] ?? '') === 'closed') return null;
        $now ??= time();
        $in = empty($c['lastInboundAt']) ? null : strtotime($c['lastInboundAt'] . ' UTC');
        $out = empty($c['lastOutboundAt']) ? null : strtotime($c['lastOutboundAt'] . ' UTC');
        if (!empty($c['needsManualMatch'])) return ['priority' => 1, 'reason' => '身份尚未确认', 'action' => '核对平台身份与客户关联后再跟进'];
        if (($c['status'] ?? '') === 'waitingApproval') return ['priority' => 1, 'reason' => '回复草稿等待审核', 'action' => '由有权限的负责人核对草稿依据并人工处理'];
        if ($in && (!$out || $in > $out) && $now - $in >= 86400) return ['priority' => 1, 'reason' => '最近客户消息超过 24 小时未回复', 'action' => '阅读原始询盘，核实需求后人工回复'];
        $last = empty($c['lastMessageAt']) ? null : strtotime($c['lastMessageAt'] . ' UTC');
        if ($last && $now - $last >= 7 * 86400) return ['priority' => 3, 'reason' => '超过 7 天无新沟通', 'action' => '核实项目是否仍在推进，决定是否人工跟进'];
        return null;
    }
}
