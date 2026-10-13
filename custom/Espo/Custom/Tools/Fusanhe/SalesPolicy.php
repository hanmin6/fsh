<?php
namespace Espo\Custom\Tools\Fusanhe;

use DateTimeImmutable;
use DateTimeZone;

/** Deterministic rules, independent of the language model and SMTP transport. */
final class SalesPolicy
{
    public const VERSION = 'zoho-sales-v1';
    public const MODEL = 'gpt-6.1-sol';
    public static function data(mixed $value): array {return json_decode(json_encode($value ?? [],JSON_THROW_ON_ERROR),true,512,JSON_THROW_ON_ERROR);}

    public static function block(array $customers, array $conversations, bool $reception = false): ?string
    {
        foreach ($customers as $c) {
            if (!empty($c['fusanheDoNotContact']) || !empty($c['emailAddressIsOptedOut']) || !empty($c['emailAddressIsInvalid']) || in_array($c['fusanheContactPolicy'] ?? '', ['optedOut', 'restricted'], true)) return 'stopped';
            if (!$reception && in_array(AcquisitionRouting::effectiveRating($c), ['S', 'A'], true)) return 'human';
            if (!empty(((array) ($c['fusanheSalesProfile'] ?? []))['paused'])) return 'human';
        }
        foreach ($conversations as $c) if (($c['controlMode'] ?? '') === 'human' && (!$reception || ($c['controlOrigin'] ?? '') !== 'valueRouting')) return 'human';
        return null;
    }

    public static function requirements(array $context): array
    {
        $p = $context['profile']; $missing = [];
        $reception = ($context['mode'] ?? '') === 'reception';
        if (!$reception && !in_array($context['rating'], ['S','A','B','C','D'], true)) $missing[] = '客户评级';
        if (!$reception && ($context['ratingReady']??true)!==true) $missing[] = '最新沟通的价值复核';
        if (!filter_var($p['email'] ?? '', FILTER_VALIDATE_EMAIL) || empty($p['emailVerified']) || empty($p['emailSource'])) $missing[] = '已核实的邮箱及来源';
        if (!$reception && (empty($p['timezoneVerified']) || !in_array($p['timezone'] ?? '', DateTimeZone::listIdentifiers(), true) || empty($p['timezoneSource']))) $missing[] = '客户时区及来源';
        if (!$reception && (empty($p['business']) || empty($p['businessSource']))) $missing[] = '客户业务及来源';
        if (!$reception && ($context['contactPolicy'] ?? '') !== 'allowed') $missing[] = '允许联系';
        if (!$reception && !$context['products']) $missing[] = '已批准的产品销售资料';
        if (empty($context['signatureApproved'])) $missing[] = '公司发件署名';
        return $missing;
    }

    /** Require an unambiguous local time; round-trip rejects DST gaps and folds. */
    public static function time(string $local, string $timezone, string $utc, int $now): string
    {
        if (!in_array($timezone, DateTimeZone::listIdentifiers(), true)) throw new \RuntimeException('sales_invalid_timezone');
        $date = DateTimeImmutable::createFromFormat('!Y-m-d H:i:s', $local, new DateTimeZone($timezone));
        $u = DateTimeImmutable::createFromFormat('!Y-m-d H:i:s', $utc, new DateTimeZone('UTC'));
        if (!$date || !$u || $date->format('Y-m-d H:i:s') !== $local || $u->format('Y-m-d H:i:s') !== $utc || $date->getTimestamp() !== $u->getTimestamp()) throw new \RuntimeException('sales_time_mismatch');
        if ($u->getTimestamp() < $now + 60 || $u->getTimestamp() > $now + 30*86400) throw new \RuntimeException('sales_invalid_due_time');
        if ((int) $date->format('N') > 5 || (int) $date->format('H') < 9 || (int) $date->format('H') >= 18) throw new \RuntimeException('sales_outside_contact_window');
        return $utc;
    }

    public static function classify(string $from, string $subject, string $body, array $headers = []): string
    {
        $text = mb_strtolower($subject . '\n' . mb_substr($body, 0, 5000));
        if (preg_match('/mailer-daemon|postmaster/i', $from) || preg_match('/delivery (?:status notification|failure)|undeliver(?:able|ed)|退信|投递失败/u', $text)) return 'bounce';
        if (!empty($headers['autoSubmitted']) && strtolower($headers['autoSubmitted']) !== 'no' || preg_match('/^(?:auto(?:matic)?[ -]?reply|out of office|自动回复)/iu', $subject)) return 'autoReply';
        if (preg_match('/(?:no[.-]?reply|notifications?|accounts?|security)@/i', $from) || preg_match('/welcome to zoho|security alert|password (?:changed|reset)|new sign.in|欢迎.*zoho|密码.*(?:更改|重置)|登录.*(?:提醒|通知)/iu', $text)) return 'system';
        return 'customer';
    }
    public static function refusal(string $text): bool
    {
        return (bool)preg_match('/(?:please\s+unsubscribe|unsubscribe\s+me|remove\s+me\s+from|stop\s+(?:emailing|contacting|sending)|do\s+not\s+(?:email|contact)|don.t\s+(?:email|contact)|不要(?:再)?(?:联系|发(?:送)?(?:邮件|消息))|停止(?:联系|发送)|请退订|取消订阅)/iu',$text);
    }
    public static function replyText(string $text): string
    {
        $head=preg_split('/^(?:On .+wrote:|-{2,}\s*Original Message\s*-{2,}|From:|发件人[:：])/imu',$text)[0];
        return trim(preg_replace('/^>.*$/m','',$head));
    }

    public static function hash(array $context): string
    {
        unset($context['nowUtc'], $context['candidateTimes']);
        // Company rest boundaries only invalidate rest-time intake. Acquired sales use customer time.
        if (($context['mode']??'')!=='reception')unset($context['receptionActive'],$context['receptionRevision']);
        return hash('sha256', json_encode($context, JSON_UNESCAPED_UNICODE | JSON_THROW_ON_ERROR));
    }
}
