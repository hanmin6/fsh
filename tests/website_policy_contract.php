<?php
/** Pure validation: no contact data, API credentials or customer sends. */
require dirname(__DIR__).'/custom/Espo/Custom/Tools/Fusanhe/WebsitePolicy.php';
require dirname(__DIR__).'/custom/Espo/Custom/Tools/Fusanhe/SalesPolicy.php';
use Espo\Custom\Tools\Fusanhe\{WebsitePolicy,SalesPolicy};
$checks=0;function ck(bool $v,string $label){global $checks;if(!$v)throw new RuntimeException($label);$checks++;}
$base=['id'=>'form-test-12345','conversation'=>'form-test-12345','kind'=>'form','role'=>'user','timestamp'=>time(),'body'=>'需要产品资料','data'=>['email'=>'buyer@example.test','name'=>'<b>Buyer</b>','ip'=>'private','key'=>'secret','landing_page'=>'https://fshfoodingredients.com/contact/?type=sample']];
$v=WebsitePolicy::event($base);ck($v['data']['name']==='Buyer','HTML stripped');ck(!isset($v['data']['ip'],$v['data']['key']),'Credentials and visitor fingerprints not exported');ck(WebsitePolicy::language($v)==='zh','Customer language preserved');ck($v['role']==='user','Form remains customer inbound');
$off=$base;$off['data']['landing_page']='https://fshfoodingredients.com.evil.test/contact';ck(!isset(WebsitePolicy::event($off)['data']['landing_page']),'Outside site source links rejected');
// BadRequest belongs to Espo, so invalid data is covered inside the native contract.
$new=WebsitePolicy::event(array_replace($base,['kind'=>'chat','role'=>'human','humanTakeover'=>true]));ck($new['humanTakeover']===true&&$new['role']==='human','Staff replies are not labelled AI');
echo "PASS $checks website policy assertions\n";
