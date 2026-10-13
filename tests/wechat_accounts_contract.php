<?php
require __DIR__ . '/../custom/Espo/Custom/Tools/Fusanhe/WeChatApi.php';
require __DIR__ . '/../custom/Espo/Custom/Tools/Fusanhe/WeChatAccounts.php';
use Espo\Custom\Tools\Fusanhe\WeChatApi;
use Espo\Custom\Tools\Fusanhe\WeChatAccounts;
final class FakeWeChatApi extends WeChatApi
{
    public int $serial = 0;
    public int $sent = 0;
    public array $login = ['status' => 'wait'];
    public array $sendResult = ['ret' => 0];
    public ?Closure $duringPoll = null;
    public ?Closure $duringUpdates = null;
    public bool $failQr = false;
    public bool $timeoutSend = false;
    public function request(string $method, string $base, string $endpoint, ?array $body = null, string $token = '', int $timeout = 10): array
    {
        if (str_contains($endpoint, 'get_bot_qrcode')) {
            if ($this->failQr) throw new RuntimeException('wechat_unavailable');
            $n = ++$this->serial; return ['qrcode' => 'private-qr-' . $n, 'qrcode_img_content' => 'https://liteapp.weixin.qq.com/q?code=' . $n];
        }
        if (str_contains($endpoint, 'get_qrcode_status')) {
            if ($this->duringPoll) { $fn = $this->duringPoll; $this->duringPoll = null; $fn(); }
            return $this->login;
        }
        if (str_contains($endpoint, 'getupdates')) {
            if ($this->duringUpdates) { $fn = $this->duringUpdates; $this->duringUpdates = null; $fn(); }
            return ['ret' => 0, 'msgs' => [['from_user_id' => 'scanner-a', 'context_token' => 'private-context']], 'get_updates_buf' => 'private-cursor'];
        }
        if (str_contains($endpoint, 'sendmessage')) { $this->sent++; if ($this->timeoutSend) throw new RuntimeException('wechat_timeout'); return $this->sendResult; }
        throw new RuntimeException('Unexpected endpoint');
    }
}
function check(bool $v, string $message): void { if (!$v) throw new RuntimeException($message); }
function denied(callable $fn, string $code): void { try { $fn(); } catch (InvalidArgumentException $e) { check($e->getMessage() === $code, 'wrong validation code'); return; } throw new RuntimeException('expected rejection ' . $code); }
$dir = sys_get_temp_dir() . '/fsh-wechat-test-' . bin2hex(random_bytes(8));
$now = 1791770000; $api = new FakeWeChatApi(); $service = new WeChatAccounts($api, $dir . '/accounts.json', function () use (&$now) { return $now; });
try {
    check(WeChatApi::acknowledgement(['message_id' => '18446744073709551615']) === true, 'optional ret with server uint64 acknowledgement');
    foreach ([[], ['errcode'=>0], ['message_id'=>'0'], ['message_id'=>true], ['message_id'=>'bogus'], ['message_id'=>'18446744073709551616'], ['ret'=>null], ['ret'=>'bogus','message_id'=>'123']] as $response) check(WeChatApi::acknowledgement($response) === null, 'missing or malformed acknowledgement accepted');
    check(WeChatApi::acknowledgement(['ret'=>-1,'message_id'=>'123']) === false && WeChatApi::acknowledgement(['ret'=>0,'errcode'=>-1]) === false, 'explicit error overrides message id or zero ret');
    denied(fn() => $service->create(' '), 'invalid_name');
    $a = $service->create('负责人'); $b = $service->create('销售主管');
    $a = $service->update($a['id'], 'refreshQr'); $b = $service->update($b['id'], 'refreshQr');
    check($a['qr']['url'] !== $b['qr']['url'] && $a['qr']['version'] !== $b['qr']['version'], 'different accounts share QR');
    check(!str_contains(json_encode($service->listing()), 'private-qr'), 'raw polling code exposed');
    $old = $a['qr']['version']; $now += 4;
    $api->login = ['status' => 'confirmed', 'bot_token' => 'secret-token', 'ilink_user_id' => 'scanner-a', 'ilink_bot_id' => 'bot-a', 'baseurl' => WeChatApi::BASE];
    $api->duringPoll = function () use ($service, $a) { $service->update($a['id'], 'refreshQr'); };
    $a = $service->update($a['id'], 'poll', ['version' => $old]);
    check($a['status'] === 'unbound' && $a['qr']['version'] !== $old, 'stale QR confirmation committed');
    $a = $service->update($a['id'], 'poll', ['version' => $a['qr']['version']]);
    check($a['status'] === 'bound' && $a['qr'] === null, 'confirmation not saved');
    $b = $service->update($b['id'], 'poll', ['version' => $b['qr']['version']]);
    check($b['status'] === 'unbound' && $b['error'] === 'duplicate_wechat', 'same WeChat allowed twice');
    check(!str_contains(json_encode($service->listing()), 'secret-token'), 'bot token leaked');
    check(!str_contains(json_encode($service->listing()), 'scanner-a'), 'full scanner id leaked');
    $a = $service->update($a['id'], 'test');
    check($a['testStatus'] === 'sent' && $api->sent === 1 && $a['lastInboundAt'] !== null, 'real acknowledgement required');
    check(!str_contains(json_encode($service->listing()), 'private-context') && !str_contains(json_encode($service->listing()), 'private-cursor'), 'context secrets leaked');
    denied(fn() => $service->update($a['id'], 'test'), 'test_too_frequent');
    $now += 31; $api->sendResult = ['message_id' => '18446744073709551615'];
    $a = $service->update($a['id'], 'test'); check($a['testStatus'] === 'sent', 'Tencent optional ret reply not recognized');
    $now += 31; $api->sendResult = [];
    $a = $service->update($a['id'], 'test'); check($a['testStatus'] === 'uncertain', 'missing acknowledgement counted as success or definite failure');
    $now += 31; $api->timeoutSend = true;
    $a = $service->update($a['id'], 'test'); check($a['testStatus'] === 'uncertain', 'timeout counted as success');
    $now += 31; $api->timeoutSend = false; $sent = $api->sent;
    $api->duringUpdates = function () use ($service, $a) { $service->update($a['id'], 'enable', ['enabled' => false]); };
    $a = $service->update($a['id'], 'test'); check($api->sent === $sent && $a['error'] === 'test_cancelled', 'disable during polling ignored');
    $a = $service->update($a['id'], 'disconnect'); check($a['status'] === 'unbound', 'disconnect did not clear credentials');
    $private = file_get_contents($dir . '/accounts.json'); check(!str_contains($private, 'secret-token'), 'disconnected token retained');
    $now += 4; $api->failQr = true;
    try { $service->update($b['id'], 'refreshQr'); } catch (RuntimeException $e) { check($e->getMessage() === 'qr_unavailable', 'raw network error leaked'); }
    $list = $service->listing(); check($list['accounts'][1]['qr']['state'] === 'error', 'failed refresh has no recovery state');
    $api->failQr = false; $now += 4; $b = $service->update($b['id'], 'refreshQr'); $now += 301;
    $b = $service->update($b['id'], 'poll', ['version' => $b['qr']['version']]); check($b['qr']['state'] === 'expired' && $b['qr']['url'] === null, 'expired QR still exposed');
    check((fileperms($dir . '/accounts.json') & 0777) === 0600, 'private credential mode');
    $service->update($a['id'], 'remove');
    check(count($service->listing()['accounts']) === 1, 'archived account still visible');
    denied(fn() => $service->update($a['id'], 'refreshQr'), 'account_not_found');
    foreach (['http://ilinkai.weixin.qq.com', 'https://weixin.qq.com.evil.test', 'https://user@ilinkai.weixin.qq.com', 'https://ilinkai.weixin.qq.com:8443', 'https://127.0.0.1'] as $url) check(!WeChatApi::trustedUrl($url), 'untrusted URL accepted');
    echo "PASS: independent QR, stale confirmation, duplicate scanner, secret filtering, send acknowledgement, cancellation, expiry, storage permissions and endpoint validation\n";
} finally { foreach (glob($dir . '/*') ?: [] as $file) unlink($file); if (is_dir($dir)) rmdir($dir); }
