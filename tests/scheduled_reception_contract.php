<?php
namespace Espo\Core\Exceptions {class BadRequest extends \RuntimeException{} class Conflict extends \RuntimeException{}}
namespace Espo\Custom\Tools\Fusanhe\Api {class RequestContext{public static function requestId(){return null;}}}
namespace Espo\ORM {
class Entity {
 public function __construct(private string $type,private array $v){}
 public function get(string $f):mixed{return $this->v[$f]??null;}
 public function set(array|string $f,mixed $v=null):void{$this->v=array_merge($this->v,is_array($f)?$f:[$f=>$v]);}
 public function getId():string{return $this->get('id');}
 public function getValueMap():object{return (object)$this->v;}
 public function getEntityType():string{return $this->type;}
}
class Repo {
 private array $where=[];private array $orders=[];
 public function __construct(private array $rows){}
 public function where(array $w):self{$this->where=$w;return $this;}
 public function order(string $f,string $dir='ASC'):self{$this->orders[]=[$f,$dir];return $this;}
 public function find():array{
  $rows=array_values(array_filter($this->rows,function($e){foreach($this->where as $k=>$v){preg_match('/^(.+?)(>=|!=)?$/',$k,$m);$a=$e->get($m[1]);$op=$m[2]??'=';$match=match($op){'>='=>$a!==null&&$a>=$v,'!='=>$a!==$v,default=>is_array($v)?in_array($a,$v,true):$a===$v};if(!$match)return false;}return true;}));
  usort($rows,function($a,$b){foreach($this->orders as [$f,$dir]){$cmp=strcmp((string)$a->get($f),(string)$b->get($f));if($cmp)return $dir==='DESC'?-$cmp:$cmp;}return 0;});return $rows;
 }
 public function findOne():?Entity{return $this->find()[0]??null;}
}
class Tx{function start(){}function commit(){}function rollback(){}}
class EntityManager{
 public array $rows=[];private int $next=0;
 public function getRDBRepository(string $t):Repo{return new Repo($this->rows[$t]??[]);}
 public function getEntityById(string $t,string $id):?Entity{return $this->rows[$t][$id]??null;}
 public function getNewEntity(string $t):Entity{return new Entity($t,['id'=>'new'.++$this->next]);}
 public function saveEntity(Entity $e,array $o=[]):void{$this->rows[$e->getEntityType()][$e->getId()]=$e;}
 public function getTransactionManager():Tx{return new Tx();}
}
}
namespace {
$root=getcwd();foreach(['ReceptionSchedule','ReceptionSettings','TextGateway','HistorySignals','ReceptionReply','ServiceKernel','AcquisitionRouting','ScheduledReceptionService'] as $f)require "$root/custom/Espo/Custom/Tools/Fusanhe/$f.php";
use Espo\Custom\Tools\Fusanhe\{ReceptionSchedule,ReceptionSettings,ReceptionReply,TextGateway,ServiceKernel,ScheduledReceptionService};
use Espo\ORM\{Entity,EntityManager};
function ck(bool $ok,string $msg):void{if(!$ok)throw new \RuntimeException($msg);}
$dir=sys_get_temp_dir().'/reception-contract-'.bin2hex(random_bytes(6));mkdir($dir);chdir($dir);mkdir('data/fusanhe',0770,true);
try{
$em=new EntityManager();$kernel=new ServiceKernel($em);$settings=new ReceptionSettings($kernel);
$config=ReceptionSchedule::defaults();$config['enabled']=true;$today=(new DateTimeImmutable('now',new DateTimeZone('Asia/Shanghai')))->format('Y-m-d');$config['dateOverrides']=[$today=>'rest'];
$config=$settings->update($config,'synthetic-admin');$config['activatedAt']=gmdate('Y-m-d H:i:s',time()-60);file_put_contents(ReceptionSettings::path(),json_encode($config));
try{$settings->update(ReceptionSchedule::defaults(),'stale-admin');throw new RuntimeException('stale revision accepted');}catch(\Espo\Core\Exceptions\Conflict $e){}
putenv('FUSANHE_TEXT_ENABLED=true');putenv('FUSANHE_TEXT_API_KEY=synthetic');putenv('FUSANHE_TEXT_API_BASE_URL=https://relay.example/v1');putenv('FUSANHE_TEXT_DEFAULT_MODEL=gpt');putenv('FUSANHE_TEXT_MODEL_GPT=gpt-6.1-sol');
$calls=0;$gateway=new TextGateway(function($url,$payload)use(&$calls){$calls++;ck(!str_contains(json_encode($payload),'private-buyer'),'private original message must stay local');return [200,json_encode(['status'=>'completed','model'=>'gpt-6.1-sol','output'=>[['content'=>[['type'=>'output_text','text'=>'{"replyKey":"price","draftText":"invented price 1 dollar"}']]]]])];});
$service=new ScheduledReceptionService($em,$kernel,new ReceptionReply($gateway));
$channel=new Entity('ExternalChannel',['id'=>'channel','type'=>'Alibaba','config'=>['realOutbound'=>true]]);
$lead=new Entity('Lead',['id'=>'lead','rating'=>'S']);
$conversation=new Entity('ExternalConversation',['id'=>'conversation','name'=>'Synthetic buyer','channelId'=>'channel','leadId'=>'lead','controlMode'=>'human','controlOrigin'=>'valueRouting','status'=>'pending','lastInboundAt'=>gmdate('Y-m-d H:i:s',time()-5),'language'=>'en']);
$message=new Entity('ExternalMessage',['id'=>'source','conversationId'=>'conversation','direction'=>'inbound','body'=>'private-buyer asks quotation','sentAt'=>gmdate('Y-m-d H:i:s',time()-5),'createdAt'=>gmdate('Y-m-d H:i:s',time()-5),'timestampConfidence'=>'high']);
foreach([$channel,$lead,$conversation,$message] as $e)$em->rows[$e->getEntityType()][$e->getId()]=$e;
ck($service->tick()['created']===1,'new offhours high-value inbound creates one task');$task=array_values($em->rows['OutboundTask'])[0];
ck(!str_contains($task->get('contentSnapshot'),'1 dollar'),'model cannot invent business commitment');
ck($task->get('triggerType')==='scheduledReception'&&$task->get('executionMode')==='real','task provenance');
ck($service->tick()['created']===0&&$calls===1,'repeat ticks do not call model or resend');
ck($service->taskCanRun($task,$conversation),'fresh scheduled task allowed');
$lead->set('fusanheSalesProfile',['paused'=>true]);ck(!$service->taskCanRun($task,$conversation),'sales customer pause revokes platform reception');$lead->set('fusanheSalesProfile',[]);
$linked=new Entity('Account',['id'=>'linked','fusanheSalesProfile'=>['paused'=>true]]);$em->rows['Account']['linked']=$linked;$conversation->set('accountId','linked');ck(!$service->taskCanRun($task,$conversation),'linked account pause is checked even with lead');$conversation->set('accountId',null);
$conversation->set('controlOrigin','manual');ck(!$service->taskCanRun($task,$conversation),'manual takeover revokes prepared task');$conversation->set('controlOrigin','valueRouting');
$lead->set('fusanheDoNotContact',true);ck(!$service->taskCanRun($task,$conversation),'contact restriction rechecked');$lead->set('fusanheDoNotContact',false);
$em->rows['ExternalMessage']['out']=new Entity('ExternalMessage',['id'=>'out','conversationId'=>'conversation','direction'=>'outbound','sentAt'=>gmdate('Y-m-d H:i:s')]);ck(!$service->taskCanRun($task,$conversation),'human/platform outbound supersedes task');unset($em->rows['ExternalMessage']['out']);
$new=new Entity('ExternalMessage',['id'=>'new-in','conversationId'=>'conversation','direction'=>'inbound','sentAt'=>gmdate('Y-m-d H:i:s')]);$em->rows['ExternalMessage']['new-in']=$new;ck(!$service->taskCanRun($task,$conversation),'new inbound supersedes task');unset($em->rows['ExternalMessage']['new-in']);
$old=$message->get('sentAt');$message->set('sentAt',gmdate('Y-m-d H:i:s',time()-3600));ck(!$service->fresh($message,$config),'historical/backfill not contacted');$message->set('sentAt',$old);
$message->set('timestampConfidence','low');ck(!$service->fresh($message,$config),'ambiguous source time not replied to');$message->set('timestampConfidence','high');
$config['enabled']=false;$config=$settings->update($config,'admin');ck(!$service->taskCanRun($task,$conversation),'disable/revision change revokes');$result=$service->tick();ck($result['cancelled']===1,'unsent task cancelled outside window');
ck(count($em->rows['Task']??[])===1,'high-value customer handed back with task');$service->tick();ck(count($em->rows['Task'])===1,'handover idempotent');
echo "PASS orchestration: selection, privacy, provenance, dedup, cutoff, takeover, restriction, freshness and handover\n";
}finally{chdir($root);foreach(glob($dir.'/data/fusanhe/*') as $f)unlink($f);rmdir($dir.'/data/fusanhe');rmdir($dir.'/data');rmdir($dir);}
}
