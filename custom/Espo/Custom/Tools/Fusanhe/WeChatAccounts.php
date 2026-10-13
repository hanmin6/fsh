<?php
namespace Espo\Custom\Tools\Fusanhe;

/** Private account registry; only explicit public fields ever leave this class. */
final class WeChatAccounts
{
    private string $path;
    private \Closure $clock;
    public function __construct(private WeChatApi $api, ?string $path = null, ?callable $clock = null)
    {
        $this->path = $path ?? ReceptionSettings::directory() . '/wechat-accounts.json';
        $this->clock = $clock ? \Closure::fromCallable($clock) : static fn() => time();
    }
    private function now(): int { return ($this->clock)(); }
    private function protect(string $path, int $mode): void
    {
        $reference = stat(dirname($path));
        clearstatcache(true, $path); $current = stat($path);
        if (!$reference || !$current || ($current['uid'] !== $reference['uid'] && !chown($path, $reference['uid'])) ||
            ($current['gid'] !== $reference['gid'] && !chgrp($path, $reference['gid'])) || !chmod($path, $mode)) throw new \RuntimeException('storage_unavailable');
    }
    private function transaction(callable $fn): mixed
    {
        $dir = dirname($this->path);
        if (!is_dir($dir) && !mkdir($dir, 0700, true) && !is_dir($dir)) throw new \RuntimeException('storage_unavailable');
        chmod($dir, 0700);
        $lock = fopen($this->path . '.lock', 'c');
        if (!$lock) throw new \RuntimeException('storage_unavailable');
        $this->protect($this->path . '.lock', 0600);
        if (!flock($lock, LOCK_EX)) { fclose($lock); throw new \RuntimeException('storage_unavailable'); }
        try {
            $all = is_file($this->path) ? json_decode(file_get_contents($this->path), true, 128, JSON_THROW_ON_ERROR) : [];
            if (!is_array($all)) throw new \RuntimeException('storage_unavailable');
            $before = $all; $result = $fn($all);
            if ($all !== $before) {
                $tmp = tempnam($dir, 'wechat-');
                if ($tmp === false) throw new \RuntimeException('storage_unavailable');
                try {
                    $this->protect($tmp, 0600);
                    if (file_put_contents($tmp, json_encode($all, JSON_UNESCAPED_UNICODE | JSON_THROW_ON_ERROR)) === false || !rename($tmp, $this->path)) throw new \RuntimeException('storage_unavailable');
                } finally { if (is_file($tmp)) unlink($tmp); }
            }
            return $result;
        } finally { flock($lock, LOCK_UN); fclose($lock); }
    }
    private function account(array $all, string $id): array
    {
        if (!preg_match('/^[a-f0-9]{24}$/', $id) || !isset($all[$id]) || isset($all[$id]['archivedAt'])) throw new \InvalidArgumentException('account_not_found');
        return $all[$id];
    }
    private function name(string $name): string
    {
        $name = trim($name);
        if ($name === '' || mb_strlen($name) > 60 || preg_match('/[\x00-\x1f\x7f]/', $name)) throw new \InvalidArgumentException('invalid_name');
        return $name;
    }
    private function publicAccount(array $a): array
    {
        $qr = $a['qr'] ?? null;
        if ($qr && $qr['expiresAt'] <= $this->now() && !in_array($qr['state'], ['generating', 'error'], true)) $qr['state'] = 'expired';
        return ['id' => $a['id'], 'name' => $a['name'], 'enabled' => $a['enabled'],
            'status' => !empty($a['token']) ? 'bound' : 'unbound', 'boundAt' => $a['boundAt'] ?? null,
            'lastInboundAt' => $a['lastInboundAt'] ?? null, 'lastTestAt' => $a['lastTestAt'] ?? null,
            'testStatus' => $a['testStatus'] ?? null, 'error' => $a['error'] ?? null,
            'agentEnabled' => $a['agentEnabled'] ?? true, 'lastAgentAt' => $a['lastAgentAt'] ?? null,
            'agentStatus' => $a['agentStatus'] ?? null,
            'qr' => $qr ? ['version' => $qr['version'], 'url' => in_array($qr['state'], ['wait', 'scaned', 'need_verifycode'], true) ? ($qr['url'] ?? null) : null,
                'expiresAt' => gmdate('c', $qr['expiresAt']), 'state' => $qr['state']] : null];
    }
    public function listing(): array
    {
        return $this->transaction(fn(array &$all) => ['accounts' => array_values(array_map(fn($a) => $this->publicAccount($a), array_filter($all, fn($a) => !isset($a['archivedAt'])))), 'canManage' => true]);
    }
    public function create(string $name): array
    {
        $name = $this->name($name); $id = bin2hex(random_bytes(12));
        return $this->transaction(function (array &$all) use ($name, $id) {
            $all[$id] = ['id' => $id, 'name' => $name, 'enabled' => true, 'agentEnabled' => true, 'agentActivatedAt' => $this->now(), 'createdAt' => $this->now()];
            return $this->publicAccount($all[$id]);
        });
    }
    public function update(string $id, string $action, array $input = []): array
    {
        if ($action === 'refreshQr') return $this->refresh($id);
        if ($action === 'poll' || $action === 'verify') return $this->poll($id, (string) ($input['version'] ?? ''), $action === 'verify' ? (string) ($input['code'] ?? '') : '');
        if ($action === 'test') return $this->test($id);
        return $this->transaction(function (array &$all) use ($id, $action, $input) {
            $a = $this->account($all, $id);
            if ($action === 'rename') $a['name'] = $this->name((string) ($input['name'] ?? ''));
            elseif ($action === 'enable') {
                if (!isset($input['enabled']) || !is_bool($input['enabled'])) throw new \InvalidArgumentException('invalid_enabled');
                $a['enabled'] = $input['enabled'];
            } elseif ($action === 'agent') {
                if (!is_bool($input['enabled'] ?? null)) throw new \InvalidArgumentException('invalid_enabled');
                $a['agentEnabled'] = $input['enabled']; $a['agentActivatedAt'] = $this->now();
                unset($a['agentSession']);
            } elseif ($action === 'cancelQr') {
                $a['qr'] = null; $a['error'] = null;
            } elseif ($action === 'disconnect' || $action === 'remove') {
                $a = ['id' => $a['id'], 'name' => $a['name'], 'enabled' => false, 'createdAt' => $a['createdAt']];
                if ($action === 'remove') $a['archivedAt'] = $this->now();
            } else throw new \InvalidArgumentException('invalid_action');
            $all[$id] = $a; return $this->publicAccount($a);
        });
    }
    private function refresh(string $id): array
    {
        $version = bin2hex(random_bytes(16));
        $tokens = $this->transaction(function (array &$all) use ($id, $version) {
            $a = $this->account($all, $id);
            if (($a['lastQrAt'] ?? 0) > $this->now() - 3) throw new \InvalidArgumentException('qr_too_frequent');
            $a['qr'] = ['version' => $version, 'state' => 'generating', 'expiresAt' => $this->now() + 300];
            $a['lastQrAt'] = $this->now(); $a['error'] = null; $all[$id] = $a;
            return array_slice(array_values(array_filter(array_column($all, 'token'))), -10);
        });
        try {
            $data = $this->api->request('POST', WeChatApi::BASE, 'ilink/bot/get_bot_qrcode?bot_type=3', ['local_token_list' => $tokens]);
            $url = $data['qrcode_img_content'] ?? ''; $code = $data['qrcode'] ?? '';
            if (!is_string($url) || strlen($url) > 8192 || !WeChatApi::trustedUrl($url) || !is_string($code) || $code === '') throw new \RuntimeException('wechat_invalid_response');
            return $this->transaction(function (array &$all) use ($id, $version, $url, $code) {
                $a = $this->account($all, $id);
                if (($a['qr']['version'] ?? '') === $version) {
                    $a['qr'] = ['version' => $version, 'state' => 'wait', 'expiresAt' => $this->now() + 300, 'url' => $url, 'code' => $code, 'base' => WeChatApi::BASE];
                    $all[$id] = $a;
                }
                return $this->publicAccount($a);
            });
        } catch (\RuntimeException $e) {
            $this->transaction(function (array &$all) use ($id, $version) {
                if (($all[$id]['qr']['version'] ?? '') === $version) { $all[$id]['qr']['state'] = 'error'; $all[$id]['error'] = 'qr_unavailable'; }
            });
            throw new \RuntimeException('qr_unavailable');
        }
    }
    private function poll(string $id, string $version, string $code): array
    {
        if ($code !== '' && !preg_match('/^[0-9]{4,12}$/', $code)) throw new \InvalidArgumentException('invalid_code');
        $a = $this->transaction(fn(array &$all) => $this->account($all, $id)); $qr = $a['qr'] ?? null;
        if (!$qr || $qr['version'] !== $version || $qr['expiresAt'] <= $this->now() || !in_array($qr['state'], ['wait', 'scaned', 'need_verifycode'], true)) return $this->publicAccount($a);
        $endpoint = 'ilink/bot/get_qrcode_status?qrcode=' . rawurlencode($qr['code']);
        if ($code !== '') $endpoint .= '&verify_code=' . rawurlencode($code);
        try { $data = $this->api->request('GET', $qr['base'], $endpoint, null, '', 5); }
        catch (\RuntimeException $e) {
            if ($e->getMessage() === 'wechat_timeout') return $this->publicAccount($this->transaction(fn(array &$all) => $this->account($all, $id)));
            throw new \RuntimeException('poll_unavailable');
        }
        return $this->transaction(function (array &$all) use ($id, $version, $data) {
            $a = $this->account($all, $id);
            if (($a['qr']['version'] ?? '') !== $version || $a['qr']['expiresAt'] <= $this->now()) return $this->publicAccount($a);
            $state = $data['status'] ?? 'wait';
            if ($state === 'confirmed') {
                $token = $data['bot_token'] ?? ''; $user = $data['ilink_user_id'] ?? ''; $bot = $data['ilink_bot_id'] ?? ''; $base = $data['baseurl'] ?? WeChatApi::BASE;
                if (!is_string($token) || $token === '' || !is_string($user) || $user === '' || !is_string($bot) || $bot === '' || !is_string($base) || !WeChatApi::trustedUrl($base)) throw new \RuntimeException('wechat_invalid_response');
                foreach ($all as $otherId => $other) {
                    if ($otherId !== $id && !empty($other['token']) && ($other['userId'] ?? '') === $user) {
                        $a['qr']['state'] = 'error'; $a['error'] = 'duplicate_wechat'; $all[$id] = $a; return $this->publicAccount($a);
                    }
                }
                unset($a['contextToken'], $a['syncBuf'], $a['lastInboundAt'], $a['lastTestAt'], $a['testStatus'], $a['agentInbox'], $a['agentSession'], $a['agentSeen']);
                $a['agentActivatedAt'] = $this->now();
                $a['token'] = $token; $a['userId'] = $user; $a['botId'] = $bot; $a['base'] = $base; $a['boundAt'] = gmdate('c', $this->now());
                $a['enabled'] = true; $a['qr'] = null; $a['error'] = null;
            } elseif ($state === 'scaned_but_redirect') {
                $host = $data['redirect_host'] ?? '';
                if (!is_string($host) || !preg_match('/^[a-z0-9.-]+$/i', $host) || !WeChatApi::trustedUrl('https://' . $host)) throw new \RuntimeException('wechat_invalid_response');
                $a['qr']['base'] = 'https://' . $host; $a['qr']['state'] = 'scaned';
            } elseif ($state === 'binded_redirect') {
                $a['qr']['state'] = 'error'; $a['error'] = 'already_bound';
            } elseif ($state === 'verify_code_blocked') {
                $a['qr']['state'] = 'error'; $a['error'] = 'code_blocked';
            } elseif (in_array($state, ['wait', 'scaned', 'need_verifycode', 'expired'], true)) {
                $a['qr']['state'] = $state;
            } else throw new \RuntimeException('wechat_invalid_response');
            $all[$id] = $a; return $this->publicAccount($a);
        });
    }
    private function test(string $id): array
    {
        $clientId = 'fsh-test-' . bin2hex(random_bytes(12));
        $a = $this->transaction(function (array &$all) use ($id, $clientId) {
            $a = $this->account($all, $id);
            if (empty($a['token'])) throw new \InvalidArgumentException('account_unbound');
            if (!$a['enabled']) throw new \InvalidArgumentException('account_disabled');
            if (($a['lastTestAttempt'] ?? 0) > $this->now() - 30) throw new \InvalidArgumentException('test_too_frequent');
            $a['lastTestAttempt'] = $this->now(); $a['testLease'] = $clientId; $all[$id] = $a; return $a;
        });
        $submitted = false;
        try {
            try {
                $updates = $this->api->request('POST', $a['base'], 'ilink/bot/getupdates', ['get_updates_buf' => $a['syncBuf'] ?? '', 'base_info' => WeChatApi::info()], $a['token'], 4);
                $this->absorb($a, $updates);
            } catch (\RuntimeException $e) { if ($e->getMessage() !== 'wechat_timeout') throw $e; }
            // Recheck revocation after polling and before submitting the notification.
            $allowed = $this->transaction(function (array &$all) use ($id, $a, $clientId) {
                $current = $this->account($all, $id);
                if (($current['token'] ?? '') !== $a['token'] || !$current['enabled'] || ($current['testLease'] ?? '') !== $clientId) return false;
                foreach (['contextToken', 'syncBuf', 'lastInboundAt'] as $field) if (isset($a[$field])) $all[$id][$field] = $a[$field];
                $this->mergeInbox($all[$id], $a);
                return true;
            });
            if (!$allowed) throw new \RuntimeException('test_cancelled');
            $msg = ['from_user_id' => '', 'to_user_id' => $a['userId'], 'client_id' => $clientId, 'message_type' => 2, 'message_state' => 2,
                'item_list' => [['type' => 1, 'text_item' => ['text' => '福三和 CRM 微信接入测试：提醒通道已绑定。每日晨报的开关和发送记录可在 CRM「微信接入」查看。']]]];
            if (!empty($a['contextToken'])) $msg['context_token'] = $a['contextToken'];
            $submitted = true;
            $result = $this->api->request('POST', $a['base'], 'ilink/bot/sendmessage', ['msg' => $msg, 'base_info' => WeChatApi::info()], $a['token'], 10);
            $ack = WeChatApi::acknowledgement($result);
            if ($ack === null) throw new \RuntimeException('wechat_invalid_response');
            if (!$ack) throw new \RuntimeException('test_rejected');
            return $this->transaction(function (array &$all) use ($id, $clientId) {
                $a = $this->account($all, $id);
                if (($a['testLease'] ?? '') === $clientId) { $a['lastTestAt'] = gmdate('c', $this->now()); $a['testStatus'] = 'sent'; $a['error'] = null; $all[$id] = $a; }
                return $this->publicAccount($a);
            });
        } catch (\RuntimeException $e) {
            $error = $submitted && in_array($e->getMessage(), ['wechat_timeout', 'wechat_unavailable', 'wechat_invalid_response'], true) ? 'test_uncertain' : ($e->getMessage() === 'test_cancelled' ? 'test_cancelled' : 'test_rejected');
            return $this->transaction(function (array &$all) use ($id, $clientId, $error) {
                $a = $this->account($all, $id);
                if (($a['testLease'] ?? '') === $clientId) { $a['testStatus'] = $error === 'test_uncertain' ? 'uncertain' : 'failed'; $a['error'] = $error; $all[$id] = $a; }
                return $this->publicAccount($a);
            });
        }
    }
    /** Durable per-account claim. Ambiguous submissions are never automatically resent. */
    public function sendReport(string $id, string $key, string $text): array
    {
        if (!preg_match('/^morning-\d{4}-\d{2}-\d{2}$/D', $key) || $text === '' || mb_strlen($text) > 4000) throw new \InvalidArgumentException('invalid_report');
        $clientId = 'fsh-' . substr(hash('sha256', $id . '|' . $key), 0, 40);
        $claim = $this->transaction(function (array &$all) use ($id, $key, $clientId) {
            $a = $this->account($all, $id);
            if (isset($a['reportDeliveries'][$key])) return ['existing' => $a['reportDeliveries'][$key]];
            if (empty($a['token']) || !$a['enabled']) return ['existing' => ['status' => 'skipped', 'error' => empty($a['token']) ? 'account_unbound' : 'account_disabled']];
            $a['reportDeliveries'][$key] = ['status' => 'preparing', 'clientId' => $clientId, 'at' => gmdate('c', $this->now())];
            $all[$id] = $a; return ['account' => $a];
        });
        if (isset($claim['existing'])) return $claim['existing'];
        $a = $claim['account']; $submitted = false;
        try {
            try {
                $updates = $this->api->request('POST', $a['base'], 'ilink/bot/getupdates', ['get_updates_buf' => $a['syncBuf'] ?? '', 'base_info' => WeChatApi::info()], $a['token'], 4);
                if (isset($updates['ret']) && (int) $updates['ret'] !== 0) throw new \RuntimeException('report_context_unavailable');
                $this->absorb($a, $updates);
            } catch (\RuntimeException $e) { if ($e->getMessage() !== 'wechat_timeout') throw $e; }
            if (empty($a['contextToken'])) throw new \RuntimeException('report_context_unavailable');
            $allowed = $this->transaction(function (array &$all) use ($id, $key, $a, $clientId) {
                $current = $this->account($all, $id);
                if (($current['token'] ?? '') !== $a['token'] || !$current['enabled'] || ($current['reportDeliveries'][$key]['clientId'] ?? '') !== $clientId) return false;
                foreach (['contextToken', 'syncBuf', 'lastInboundAt'] as $field) if (isset($a[$field])) $all[$id][$field] = $a[$field];
                $this->mergeInbox($all[$id], $a);
                // Persist uncertainty BEFORE the external side effect, including process crashes.
                $all[$id]['reportDeliveries'][$key]['status'] = 'uncertain';
                return true;
            });
            if (!$allowed) throw new \RuntimeException('report_cancelled');
            $msg = ['from_user_id' => '', 'to_user_id' => $a['userId'], 'client_id' => $clientId, 'message_type' => 2, 'message_state' => 2,
                'item_list' => [['type' => 1, 'text_item' => ['text' => $text]]]];
            if (!empty($a['contextToken'])) $msg['context_token'] = $a['contextToken'];
            $submitted = true;
            $result = $this->api->request('POST', $a['base'], 'ilink/bot/sendmessage', ['msg' => $msg, 'base_info' => WeChatApi::info()], $a['token'], 10);
            $ack = WeChatApi::acknowledgement($result);
            if ($ack === null) throw new \RuntimeException('wechat_invalid_response');
            $delivery = ['status' => $ack ? 'sent' : 'failed', 'error' => $ack ? null : 'report_rejected', 'at' => gmdate('c', $this->now())];
        } catch (\Throwable $e) {
            $uncertain = $submitted && in_array($e->getMessage(), ['wechat_timeout', 'wechat_unavailable', 'wechat_invalid_response'], true);
            $delivery = ['status' => $uncertain ? 'uncertain' : 'failed', 'error' => $uncertain ? 'report_uncertain' : ($e->getMessage() === 'report_cancelled' ? 'report_cancelled' : 'report_context_unavailable'), 'at' => gmdate('c', $this->now())];
        }
        $this->transaction(function (array &$all) use ($id, $key, $clientId, $delivery) {
            if (($all[$id]['reportDeliveries'][$key]['clientId'] ?? '') === $clientId) {
                $all[$id]['reportDeliveries'][$key] = $delivery + ['clientId' => $clientId];
                if ($delivery['status'] === 'sent' && in_array($all[$id]['error'] ?? '', ['test_uncertain','test_rejected'], true)) $all[$id]['error'] = null;
            }
        });
        return $delivery;
    }
    private function mergeInbox(array &$current, array $incoming): void
    {
        // Preserve existing claims when another consumer fetched the same cursor.
        foreach ($incoming['agentInbox'] ?? [] as $key => $m) if (!isset($current['agentInbox'][$key]) && !isset($current['agentSeen'][$key])) $current['agentInbox'][$key] = $m;
        foreach ($incoming['agentSeen'] ?? [] as $key => $at) $current['agentSeen'][$key] = $at;
        foreach ($current['agentSeen'] ?? [] as $key => $at) if ($at < $this->now()-86400) unset($current['agentSeen'][$key]);
        $terminal = array_keys(array_filter($current['agentInbox'] ?? [], fn($m) => in_array($m['state'], ['sent','failed','uncertain','ignored'], true)));
        foreach (array_slice($terminal, 0, max(0, count($terminal)-100)) as $key) unset($current['agentInbox'][$key]);
    }
    private function absorb(array &$a, array $updates): void
    {
        if (isset($updates['ret']) && (int)$updates['ret'] !== 0 || isset($updates['errcode']) && (int)$updates['errcode'] !== 0) throw new \RuntimeException('wechat_unavailable');
        foreach ($updates['msgs'] ?? [] as $msg) {
            if (($msg['from_user_id'] ?? '') !== ($a['userId'] ?? '')) continue;
            if (!empty($msg['group_id'])) continue;
            $context = $msg['context_token'] ?? '';
            if (is_string($context) && $context !== '') { $a['contextToken'] = $context; $a['lastInboundAt'] = gmdate('c', $this->now()); }
            if (empty($a['agentEnabled']) || empty($a['agentActivatedAt']) || ($msg['message_type'] ?? 1) !== 1 || !$context) continue;
            $at = (int) floor(((float)($msg['create_time_ms'] ?? 0))/1000);
            if ($at < $a['agentActivatedAt'] || $at < $this->now()-600 || $at > $this->now()+30) continue;
            $mid = $msg['message_id'] ?? ''; if (!(is_string($mid)||is_int($mid)) || (string)$mid === '') continue;
            $text = [];
            foreach ($msg['item_list'] ?? [] as $item) {
                if (($item['type'] ?? 0) === 1 && is_string($item['text_item']['text'] ?? null)) $text[] = $item['text_item']['text'];
                if (($item['type'] ?? 0) === 3 && is_string($item['voice_item']['text'] ?? null)) $text[] = $item['voice_item']['text'];
            }
            $text = trim(implode("\n",$text)); if ($text === '' || mb_strlen($text)>4000) continue;
            $key = hash('sha256',(string)$mid);
            if (!isset($a['agentInbox'][$key]) && !isset($a['agentSeen'][$key])) {
                $a['agentInbox'][$key] = ['key'=>$key,'text'=>$text,'context'=>$context,'at'=>$at,'state'=>'queued'];
                $a['agentSeen'][$key] = $at;
            }
        }
        if (is_string($updates['get_updates_buf'] ?? null)) $a['syncBuf'] = $updates['get_updates_buf'];
    }
    public function pollInbox(string $id): void
    {
        $a=$this->transaction(fn(array &$all)=>$this->account($all,$id));
        if (empty($a['token']) || !($a['agentEnabled']??true)) return;
        $updates=$this->api->request('POST',$a['base'],'ilink/bot/getupdates',['get_updates_buf'=>$a['syncBuf']??'','base_info'=>WeChatApi::info()],$a['token'],4);
        $this->absorb($a,$updates);
        $this->transaction(function(array &$all)use($id,$a){
            $current=$this->account($all,$id);if(($current['token']??'')!==$a['token'])return;
            foreach(['contextToken','syncBuf','lastInboundAt'] as $f)if(isset($a[$f]))$all[$id][$f]=$a[$f];
            $this->mergeInbox($all[$id],$a);
        });
    }
    public function claimAgentMessage(string $id): ?array
    {
        return $this->transaction(function(array &$all)use($id){
            $a=$this->account($all,$id);if(empty($a['token'])||!($a['agentEnabled']??true))return null;
            foreach($a['agentInbox']??[] as $key=>$m){
                if($m['state']!=='queued')continue;
                if($m['at']<($a['agentActivatedAt']??PHP_INT_MAX)||$m['at']<$this->now()-600){$all[$id]['agentInbox'][$key]['state']='ignored';continue;}
                $lease=bin2hex(random_bytes(12));$all[$id]['agentInbox'][$key]['state']='working';$all[$id]['agentInbox'][$key]['lease']=$lease;
                return $m+['lease'=>$lease,'session'=>$a['agentSession']??[]];
            }
            return null;
        });
    }
    public function prepareAgentReply(string $id,string $key,string $lease,callable $execute): bool
    {
        return $this->transaction(function(array &$all)use($id,$key,$lease,$execute){
            $a=$this->account($all,$id);$m=$a['agentInbox'][$key]??[];
            if(empty($a['token'])||!($a['agentEnabled']??true)||($m['lease']??'')!==$lease||($m['state']??'')!=='working'||$m['at']<($a['agentActivatedAt']??PHP_INT_MAX))return false;
            $session=$a['agentSession']??[];$text=$execute($session);
            if(!is_string($text)||$text===''||mb_strlen($text)>4000)throw new \RuntimeException('agent_invalid_reply');
            $all[$id]['agentSession']=$session;$all[$id]['agentInbox'][$key]['reply']=$text;$all[$id]['agentInbox'][$key]['state']='ready';return true;
        });
    }
    public function sendAgentReply(string $id,string $key,string $lease,?callable $allowed=null): array
    {
        $a=$this->transaction(function(array &$all)use($id,$key,$lease,$allowed){
            $a=$this->account($all,$id);$m=$a['agentInbox'][$key]??[];
            if(empty($a['token'])||!($a['agentEnabled']??true)||($m['lease']??'')!==$lease||($m['state']??'')!=='ready'||$allowed&&!$allowed())return null;
            $all[$id]['agentInbox'][$key]['state']='uncertain';return $a;
        });
        if(!$a)return ['status'=>'cancelled'];$m=$a['agentInbox'][$key];
        try{
            $result=$this->api->request('POST',$a['base'],'ilink/bot/sendmessage',['msg'=>['from_user_id'=>'','to_user_id'=>$a['userId'],'client_id'=>'fsh-agent-'.substr(hash('sha256',$id.'|'.$key),0,40),'message_type'=>2,'message_state'=>2,'context_token'=>$m['context'],'item_list'=>[['type'=>1,'text_item'=>['text'=>$m['reply']]]]],'base_info'=>WeChatApi::info()],$a['token'],15);
            $ack=WeChatApi::acknowledgement($result);$state=$ack===true?'sent':($ack===false?'failed':'uncertain');
        }catch(\Throwable $e){$state='uncertain';}
        $this->transaction(function(array &$all)use($id,$key,$lease,$state){
            if(($all[$id]['agentInbox'][$key]['lease']??'')!==$lease)return;
            $all[$id]['agentInbox'][$key]['state']=$state;$all[$id]['lastAgentAt']=gmdate('c',$this->now());$all[$id]['agentStatus']=$state;
        });
        return ['status'=>$state];
    }
}
