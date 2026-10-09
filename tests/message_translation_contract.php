<?php
namespace Espo\Core\Exceptions {class BadRequest extends \RuntimeException{}class Forbidden extends \RuntimeException{}class NotFound extends \RuntimeException{}}
namespace Espo\ORM {
 class Entity {public array $values=[];public function __construct(private string $id){}public function getId():string{return $this->id;}public function get(string $key):mixed{return $this->values[$key]??null;}public function set(string $key,mixed $value):void{$this->values[$key]=$value;}}
 class EntityManager {public array $rows=[];public int $saves=0;public function getEntityById(string $type,string $id):?Entity{return $this->rows[$type][$id]??null;}public function saveEntity(Entity $e,array $options=[]):void{if(!($options['fusanheService']??false))throw new \RuntimeException('Service write required');$this->saves++;}}
}
namespace Espo\Entities {class User extends \Espo\ORM\Entity {public function isAdmin():bool{return false;}}}
namespace Espo\Core {class Acl {public array $denied=[];public function checkScope(string $type,string $action):bool{return !in_array($type,$this->denied,true);}public function checkEntity($entity,string $action):bool{return !in_array($entity->getId(),$this->denied,true);}public function checkField(string $type,string $field,string $action):bool{return !in_array($field,$this->denied,true);}}}
namespace Espo\Core\Api {
 interface Action{}class Request {public function __construct(public string $id,public object $input){}public function getRouteParam($name){return $this->id;}public function getParsedBody(){return $this->input;}public function getHeader($name){return null;}}
 class Response {public function __construct(public array $body){}public function setStatus($status){}public function setHeader($key,$value){}}
 class ResponseComposer {public static function json(array $body):Response{return new Response($body);}}
}
namespace {
use Espo\Custom\Tools\Fusanhe\{TextGateway,MessageTranslationPolicy,MessageTranslationService};
use Espo\Custom\Tools\Fusanhe\Api\PostTranslateMessages;
use Espo\ORM\{Entity,EntityManager};
$root=getcwd();foreach(['TextGateway','MessageTranslationPolicy','MessageTranslationService','Api/AbstractFusanheAction','Api/PostTranslateMessages'] as $name)require $root.'/custom/Espo/Custom/Tools/Fusanhe/'.$name.'.php';
function check(bool $v,string $name):void{if(!$v)throw new RuntimeException('FAIL: '.$name);}
function fails(callable $f,string $code):void{try{$f();}catch(\RuntimeException $e){check($e->getMessage()===$code,$code);return;}throw new RuntimeException('Expected: '.$code);}
$dir=sys_get_temp_dir().'/translation-test-'.bin2hex(random_bytes(6));mkdir($dir,0700);chdir($dir);
putenv('FUSANHE_TEXT_ENABLED=true');putenv('FUSANHE_TEXT_API_KEY=synthetic');putenv('FUSANHE_TEXT_API_BASE_URL=https://example.invalid/v1');putenv('FUSANHE_TEXT_MODEL_GPT=gpt-synthetic');putenv('FUSANHE_TEXT_DEFAULT_MODEL=gpt');
$em=new EntityManager();$conversation=new Entity('c1');$em->rows['ExternalConversation']['c1']=$conversation;
function msg(string $id,string $body,string $conversation='c1',?string $translation=null):Entity{global $em;$e=new Entity($id);$e->values=['body'=>$body,'conversationId'=>$conversation,'translatedBody'=>$translation,'direction'=>'inbound','sentAt'=>'2026-10-09 08:00:00','contentHash'=>hash('sha256',$body)];$em->rows['ExternalMessage'][$id]=$e;return $e;}
$a=msg('a','Please quote 1,600 cartons. SKU FS-20. buyer@example.com https://example.invalid/p/20');$original=$a->values;
msg('existing','Hello',translation:'你好');msg('chinese','请确认包装');msg('french','bonjour monsieur');msg('fail','Please confirm 25 cartons.');
$calls=0;$mode='normal';$maxInput=0;
$text=new TextGateway(function($url,$payload)use(&$calls,&$mode,&$maxInput){$calls++;check($payload['max_output_tokens']>=1600&&$payload['max_output_tokens']<=8192,'bounded output');$input=json_decode($payload['input'][1]['content'],true);$maxInput=max($maxInput,strlen(json_encode($input)));
 if($mode==='fail')return [429,'{}'];
 $rows=[];foreach($input['messages'] as $r){$body=$r['body'];$rows[]=['id'=>$r['id'],'english'=>$body!=='bonjour monsieur','translatedBody'=>$body==='bonjour monsieur'?'':'中文译文 '.$body];}
 if($mode==='unknown')$rows[0]['id']='other';if($mode==='numbers')$rows[0]['translatedBody']='中文译文';if($mode==='duplicate')$rows[]=$rows[0];
 return [200,json_encode(['model'=>'gpt-synthetic','status'=>'completed','output'=>[['content'=>[['type'=>'output_text','text'=>json_encode(['messages'=>$rows])]]]]])];});
fails(fn()=>$text->complete([['role'=>'user','content'=>'Hello']],null,true,8193),'text_invalid_output_limit');
check(MessageTranslationPolicy::validate(['messages'=>[['id'=>'hyphen','english'=>true,'translatedBody'=>'请发送高品质产品。']]],[['id'=>'hyphen','body'=>'Please send high-quality products.']])['hyphen']['english'],'ordinary hyphen words can translate');
$service=new MessageTranslationService($em,$text);
$result=$service->translate('c1',['a','existing','chinese','french']);check($calls===1,'one batch model call');check($result['messages'][0]['status']==='completed','English translated');check($result['messages'][1]['translatedBody']==='你好','platform translation reused');check($result['messages'][2]['status']==='skipped'&&$result['messages'][3]['status']==='skipped','Chinese and other language skipped');
check(array_diff_assoc($original,$a->values)===['translatedBody'=>null],'only translation changes');check($a->get('translatedBody')!==null,'persisted');
$service->translate('c1',['a','existing','chinese','french']);check($calls===1,'persistent completed/skip dedup');
$em->rows['ExternalMessage']['a']->set('translatedBody',null);$service->translate('c1',['a']);check($calls===1&&$a->get('translatedBody')!==null,'cache restores interrupted database save');
$mode='fail';$before=$calls;$bad=$service->translate('c1',['fail']);check($bad['messages'][0]['status']==='failed'&&$calls===$before+1,'safe failure');$service->translate('c1',['fail']);check($calls===$before+1,'failure cooldown prevents paid loop');$mode='normal';$service->translate('c1',['fail'],true);check($calls===$before+2,'explicit retry succeeds');
foreach(['unknown','numbers','duplicate'] as $case){$mode=$case;msg($case,'Please send 25 cartons.');$r=$service->translate('c1',[$case]);check($r['messages'][0]['status']==='failed'&&!$em->rows['ExternalMessage'][$case]->get('translatedBody'),'invalid response cannot be saved: '.$case);}
$mode='normal';$long=str_repeat("Please confirm SKU FS-20 and 25 cartons.\n",1100);msg('long',$long);$before=$calls;$r=$service->translate('c1',['long']);check($r['messages'][0]['status']==='completed'&&$calls>$before+1,'long messages split without truncation');check(substr_count($r['messages'][0]['translatedBody'],'SKU FS-20')===1100,'all long message content retained');check($maxInput<20000,'bounded model input');
$lock=fopen('data/fusanhe-message-translations/'.hash('sha256','c1').'.lock','c');flock($lock,LOCK_EX);$before=$calls;msg('locked','Hello customer');$r=$service->translate('c1',['locked']);check($r['messages'][0]['status']==='busy'&&$calls===$before,'concurrent request never duplicates paid call');flock($lock,LOCK_UN);fclose($lock);
// Every record and field is checked before any model call, including cached translations.
$acl=new \Espo\Core\Acl();$action=new PostTranslateMessages($service,new \Espo\Entities\User('u1'),$acl,$em);
$request=new \Espo\Core\Api\Request('c1',(object)['messageIds'=>['a']]);
foreach(['ExternalConversation','ExternalMessage','c1','a','body','translatedBody'] as $denied){$acl->denied=[$denied];$before=$calls;try{$action->process($request);throw new RuntimeException('ACL allowed '.$denied);}catch(\Espo\Core\Exceptions\Forbidden $e){}check($calls===$before,'ACL prevents model call');}$acl->denied=[];
msg('foreign','Hello foreign','c2');foreach([['foreign'],['missing'],[],['a','a'],array_fill(0,7,'a')] as $ids){try{$action->process(new \Espo\Core\Api\Request('c1',(object)['messageIds'=>$ids]));throw new RuntimeException('Invalid request allowed');}catch(\Espo\Core\Exceptions\BadRequest|\Espo\Core\Exceptions\NotFound $e){}}
check($action->process($request)->body['messages'][0]['translatedBody']===$a->get('translatedBody'),'reader can translate without edit permission');
// Failed DB save remains replayable without another model call.
check((fileperms('data/fusanhe-message-translations')&0777)===0700,'private cache folder');
chdir($root);$it=new RecursiveIteratorIterator(new RecursiveDirectoryIterator($dir,FilesystemIterator::SKIP_DOTS),RecursiveIteratorIterator::CHILD_FIRST);foreach($it as $f){$f->isDir()?rmdir($f->getPathname()):unlink($f->getPathname());}rmdir($dir);
echo "PASS: batch translations, persistence, no duplicate paid calls, language skip, retry, long text, validation, locking, ACL and membership\n";
}
