<?php
namespace Espo\Core\Api { interface Action {} class Request {public function __construct(public array $body=[]){} public function getQueryParam($key){return null;} public function getParsedBody(){return (object)$this->body;} public function getRouteParam($key){return '123456789012345678901234';}} class Response {} }
namespace Espo\Core {class Acl {public function checkScope($scope,$action){return true;}}}
namespace Espo\Core\Exceptions {class Forbidden extends \RuntimeException {}}
namespace Espo\Entities {class User {public function isAdmin(){return false;}}}
namespace Espo\ORM {class EntityManager {}}
namespace {
require __DIR__.'/../custom/Espo/Custom/Tools/Fusanhe/Api/AbstractFusanheAction.php';
require __DIR__.'/../custom/Espo/Custom/Tools/Fusanhe/Api/GetWeChatAccounts.php';
require __DIR__.'/../custom/Espo/Custom/Tools/Fusanhe/Api/PostWeChatAccount.php';
require __DIR__.'/../custom/Espo/Custom/Tools/Fusanhe/MorningReportStore.php';
require __DIR__.'/../custom/Espo/Custom/Tools/Fusanhe/MorningReportService.php';
require __DIR__.'/../custom/Espo/Custom/Tools/Fusanhe/Api/GetMorningReport.php';
require __DIR__.'/../custom/Espo/Custom/Tools/Fusanhe/Api/PostMorningReport.php';
require __DIR__.'/../custom/Espo/Custom/Tools/Fusanhe/Api/PostWeChatAgent.php';
$user=new \Espo\Entities\User();$acl=new \Espo\Core\Acl();$em=new \Espo\ORM\EntityManager();
$read=new \Espo\Custom\Tools\Fusanhe\Api\GetWeChatAccounts($user,$acl,$em);
$write=new \Espo\Custom\Tools\Fusanhe\Api\PostWeChatAccount($user,$acl,$em);
$count=0;
foreach(['read','refreshQr','poll','verify','test','enable','rename','remove','disconnect'] as $action){
 try{($action==='read'?$read:$write)->process(new \Espo\Core\Api\Request(['action'=>$action]));throw new \RuntimeException('Non-admin access accepted');}
 catch(\Espo\Core\Exceptions\Forbidden $e){$count++;}
}
$morningRead=new \Espo\Custom\Tools\Fusanhe\Api\GetMorningReport($user,$acl,$em);
$morningWrite=new \Espo\Custom\Tools\Fusanhe\Api\PostMorningReport($user,$acl,$em);
foreach(['read','configure','preview'] as $action){try{($action==='read'?$morningRead:$morningWrite)->process(new \Espo\Core\Api\Request(['action'=>$action]));throw new \RuntimeException('Non-admin morning management accepted');}catch(\Espo\Core\Exceptions\Forbidden $e){$count++;}}
$agent=new \Espo\Custom\Tools\Fusanhe\Api\PostWeChatAgent($user,$acl,$em);
try{$agent->process(new \Espo\Core\Api\Request(['enabled'=>true]));throw new \RuntimeException('Non-admin agent configuration accepted');}catch(\Espo\Core\Exceptions\Forbidden $e){$count++;}
echo "PASS: {$count} non-admin operations denied before storage or network access, even with broad CRM scope permissions\n";
}
