<?php
namespace Espo\ORM { class EntityManager {} }
namespace {
require __DIR__ . '/../custom/Espo/Custom/Tools/Fusanhe/WeChatApi.php';
require __DIR__ . '/../custom/Espo/Custom/Tools/Fusanhe/WeChatAccounts.php';
require __DIR__ . '/../custom/Espo/Custom/Tools/Fusanhe/ReceptionSettings.php';
require __DIR__ . '/../custom/Espo/Custom/Tools/Fusanhe/MorningReportStore.php';
require __DIR__ . '/../custom/Espo/Custom/Tools/Fusanhe/MorningReportService.php';
use Espo\Custom\Tools\Fusanhe\{WeChatApi, WeChatAccounts, MorningReportStore, MorningReportService};

final class RecoveryApi extends WeChatApi {
    public array $updates = [];
    public array $reply = ['ret' => -1];
    public array $sent = [];
    public ?\Closure $duringUpdates = null;
    public ?string $sendError = null;
    public function request(string $method, string $base, string $endpoint, ?array $body = null, string $token = '', int $timeout = 10): array {
        if (str_contains($endpoint, 'getupdates')) {
            $response = array_shift($this->updates) ?? ['ret' => 0, 'msgs' => []];
            if ($this->duringUpdates) { $f = $this->duringUpdates; $this->duringUpdates = null; $f(); }
            return $response;
        }
        if (str_contains($endpoint, 'sendmessage')) {
            $this->sent[] = $body['msg'];
            if ($this->sendError !== null) throw new \RuntimeException($this->sendError);
            return $this->reply;
        }
        throw new \RuntimeException('unexpected_fixture_endpoint');
    }
}
function recoveryCheck(bool $ok, string $message): void { if (!$ok) throw new \RuntimeException($message); }
function fixture(string $path, int &$now): array {
    $id = str_repeat('a', 24); $api = new RecoveryApi();
    $account = ['id'=>$id, 'name'=>'Fixture recipient', 'createdAt'=>1, 'enabled'=>true, 'agentEnabled'=>true,
        'agentActivatedAt'=>$now-60, 'token'=>'fixture-token', 'userId'=>'fixture-user', 'base'=>WeChatApi::BASE,
        'contextToken'=>'context-initial', 'syncBuf'=>'cursor-initial', 'lastInboundAt'=>gmdate('c',$now-10)];
    file_put_contents($path, json_encode([$id=>$account]));
    $service = new WeChatAccounts($api, $path, function () use (&$now) { return $now; });
    return [$id,$api,$service];
}
function freshContext(string $path, string $id, int $now, string $token): void {
    $all=json_decode(file_get_contents($path),true);$all[$id]['contextToken']=$token;$all[$id]['lastInboundAt']=gmdate('c',$now);
    file_put_contents($path,json_encode($all));
}
function updateMessage(string $context, string $cursor, string $id, int $now): array {
    return ['ret'=>0,'get_updates_buf'=>$cursor,'msgs'=>[['from_user_id'=>'fixture-user','context_token'=>$context,
        'message_id'=>$id,'message_type'=>1,'create_time_ms'=>$now*1000,'item_list'=>[['type'=>1,'text_item'=>['text'=>'Synthetic inquiry']]]]]];
}
$root=getcwd();$dir=sys_get_temp_dir().'/fsh-recovery-'.bin2hex(random_bytes(8));mkdir($dir,0700);chdir($dir);
$path=$dir.'/accounts.json';$cases=[];
$cases['safe rejection classification']=function () {
    foreach ([[['ret'=>-14], 'report_token_expired', -14], [['errcode'=>'-14'], 'report_token_expired',-14],
        [['ret'=>-1,'errmsg'=>'context expired fixture-secret'], 'report_context_expired',-1],
        [['ret'=>-2,'errmsg'=>'generic fixture-secret'], 'report_rejected',-2],
        [['ret'=>'invalid','errmsg'=>'fixture-secret'], 'report_rejected',null]] as [$input,$error,$code]) {
        $r=WeChatApi::rejection($input);recoveryCheck($r===['error'=>$error,'providerCode'=>$code],'rejection classification or private response leaked');
    }
};
$cases['fresh context and two retry limit']=function () use ($path) {
    $now=strtotime('2026-10-20T01:00:00Z');[$id,$api,$s]=fixture($path,$now);$key='morning-2026-10-20';
    $r=$s->sendReport($id,$key,'Immutable report');recoveryCheck($r['status']==='failed','definite rejection');
    $now+=10;freshContext($path,$id,$now,'context-initial');$s->sendReport($id,$key,'Immutable report',true);
    recoveryCheck(count($api->sent)===1,'same context must not retry');
    freshContext($path,$id,$now-20,'context-changed');$s->sendReport($id,$key,'Immutable report',true);
    recoveryCheck(count($api->sent)===1,'context predating failure must not retry');
    for($i=1;$i<=3;$i++){$now+=10;freshContext($path,$id,$now,'context-fresh-'.$i);$s->sendReport($id,$key,'Immutable report',true);}
    recoveryCheck(count($api->sent)===3,'exactly two bounded retries');
    recoveryCheck(count(array_unique(array_column($api->sent,'client_id')))===1,'same logical delivery id');
};
$cases['all submitted exceptions remain uncertain']=function () use ($path) {
    foreach(['wechat_timeout','wechat_unavailable','wechat_invalid_response','unexpected_after_submit'] as $error){
        $now=strtotime('2026-10-20T01:00:00Z');[$id,$api,$s]=fixture($path,$now);$api->sendError=$error;
        $r=$s->sendReport($id,'morning-2026-10-20','Synthetic report');recoveryCheck($r['status']==='uncertain','submitted exception reopened: '.$error);
        $now+=60;freshContext($path,$id,$now,'fresh-after-uncertain');$s->sendReport($id,'morning-2026-10-20','Synthetic report',true);
        recoveryCheck(count($api->sent)===1,'uncertain delivery must not resend');
    }
};
$cases['terminal outcomes and explicit legacy diagnosis']=function () use ($path) {
    foreach(['sent','uncertain','preparing','token-expired'] as $state){
        $now=strtotime('2026-10-20T01:00:00Z');[$id,$api,$s]=fixture($path,$now);$all=json_decode(file_get_contents($path),true);
        $all[$id]['reportDeliveries']['morning-2026-10-20']=['status'=>$state==='token-expired'?'failed':$state,'error'=>'report_token_expired','at'=>gmdate('c',$now-10)];file_put_contents($path,json_encode($all));
        freshContext($path,$id,$now,'new-context');$s->sendReport($id,'morning-2026-10-20','Synthetic',true);recoveryCheck(!$api->sent,'terminal outcome resent: '.$state);
    }
    $now=strtotime('2026-10-20T01:00:00Z');[$id,$api,$s]=fixture($path,$now);$all=json_decode(file_get_contents($path),true);
    $all[$id]['reportDeliveries']['morning-2026-10-20']=['status'=>'failed','error'=>'report_rejected','at'=>gmdate('c',$now)];file_put_contents($path,json_encode($all));
    $s->sendReport($id,'morning-2026-10-20','Synthetic',true);recoveryCheck(!$api->sent,'scheduler diagnosed legacy failure');
    $s->sendReport($id,'morning-2026-10-20','Synthetic',true,true);$s->sendReport($id,'morning-2026-10-20','Synthetic',true,true);
    recoveryCheck(count($api->sent)===1,'legacy diagnosis must require explicit one-time request');
};
$cases['same-second concurrent polling preserves latest context']=function () use ($path) {
    foreach(['report','poll','test'] as $entry){
        $now=strtotime('2026-10-20T01:00:00Z');[$id,$api,$s]=fixture($path,$now);$api->reply=['ret'=>0];
        $api->updates=[updateMessage('context-old','cursor-old','outer',$now),updateMessage('context-new','cursor-new','inner',$now)];
        $api->duringUpdates=fn()=>$s->pollInbox($id);
        if($entry==='report')$s->sendReport($id,'morning-2026-10-20','Synthetic');elseif($entry==='poll')$s->pollInbox($id);else $s->update($id,'test');
        $a=json_decode(file_get_contents($path),true)[$id];
        recoveryCheck($a['contextToken']==='context-new'&&$a['syncBuf']==='cursor-new','concurrent context rolled back: '.$entry);
        recoveryCheck(count($a['agentInbox'])===2,'concurrent inbox merge lost a message: '.$entry);
        if($entry!=='poll')recoveryCheck($api->sent[0]['context_token']==='context-new','send used stale context: '.$entry);
    }
};
$cases['late recovery never starts pending recipients']=function () use ($path) {
    $now=strtotime('2026-10-20T01:16:00Z');[$id,$api,$s]=fixture($path,$now);$api->reply=['ret'=>0];
    $store=new MorningReportStore();$store->configure(true,new \DateTimeImmutable('2026-10-19T00:00:00Z'));
    $store->save(['date'=>'2026-10-20','text'=>'Immutable synthetic','contentHash'=>hash('sha256','Immutable synthetic'),'deliveries'=>[$id=>['name'=>'Fixture','status'=>'pending']]]);
    $reports=new MorningReportService(new \Espo\ORM\EntityManager(),$store);$reports->tick(new \DateTimeImmutable(gmdate('c',$now)),$s);
    recoveryCheck(!$api->sent,'late pending recipient received first send');
    $now=strtotime('2026-10-21T01:15:00Z');$r=$reports->tick(new \DateTimeImmutable(gmdate('c',$now)),$s);
    recoveryCheck($r['due']===false&&$store->read('2026-10-21')===null,'late report generated');
};
$cases['late known rejection recovers and projection hides internals']=function () use ($path) {
    $now=strtotime('2026-10-22T01:00:00Z');[$id,$api,$s]=fixture($path,$now);$key='morning-2026-10-22';$first=$s->sendReport($id,$key,'Immutable synthetic');
    $store=new MorningReportStore();$store->save(['date'=>'2026-10-22','text'=>'Immutable synthetic','contentHash'=>hash('sha256','Immutable synthetic'),'deliveries'=>[$id=>['name'=>'Fixture']+$first]]);
    $now+=16*60;freshContext($path,$id,$now,'new-late-context');$api->reply=['ret'=>0];$reports=new MorningReportService(new \Espo\ORM\EntityManager(),$store);
    $reports->tick(new \DateTimeImmutable(gmdate('c',$now)),$s);$saved=$store->read('2026-10-22');
    recoveryCheck(count($api->sent)===2&&$saved['deliveries'][$id]['status']==='sent','late fresh-context recovery failed');
    recoveryCheck($saved['contentHash']===hash('sha256','Immutable synthetic'),'report content changed');
    recoveryCheck(!str_contains(json_encode($saved),'contextHash')&&!str_contains(json_encode($saved),'clientId'),'internal delivery fields exposed');
    recoveryCheck($reports->tick(new \DateTimeImmutable('2026-10-22T04:00:00Z'),$s)['due']===false,'retry continued at noon');
};
$failures=[];
try { foreach($cases as $name=>$case){try{$case();echo "PASS $name\n";}catch(\Throwable $e){$failures[]=$name;fwrite(STDERR,"FAIL $name: ".$e->getMessage()."\n");}} }
finally { chdir($root);$it=new \RecursiveIteratorIterator(new \RecursiveDirectoryIterator($dir,\FilesystemIterator::SKIP_DOTS),\RecursiveIteratorIterator::CHILD_FIRST);foreach($it as $p)$p->isDir()?rmdir($p->getPathname()):unlink($p->getPathname());rmdir($dir); }
exit($failures?1:0);
}
