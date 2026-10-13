<?php
/** Offline assertions: no customer data, no credentials and no network. */
$base=dirname(__DIR__).'/custom/Espo/Custom/Tools/Fusanhe/';
foreach (['AcquisitionRouting','SalesPolicy','SalesPlanner','TextGateway','SalesEnrichment'] as $file)require $base.$file.'.php';
use Espo\Custom\Tools\Fusanhe\SalesEnrichment;
use Espo\Custom\Tools\Fusanhe\{SalesPolicy,SalesPlanner,TextGateway};
$checks=0;
function ck(bool $ok,string $label): void {global $checks;if (!$ok)throw new RuntimeException($label);$checks++;}
function rejected(callable $fn,string $label): void {try{$fn();}catch(Throwable $e){ck(true,$label);return;}ck(false,$label);}
$customer=['rating'=>'B','fusanheSalesProfile'=>[]];
ck(SalesPolicy::block([$customer],[])===null,'B active sales permitted by rating');
foreach (['S','A'] as $r) {
 ck(SalesPolicy::block([['rating'=>$r]],[])==='human','High acquired proactive sales are human');
 ck(SalesPolicy::block([['rating'=>$r]],[['controlMode'=>'human','controlOrigin'=>'valueRouting']],true)===null,'Rest reception takes priority over high rating');
 ck(SalesPolicy::block([['rating'=>$r]],[['controlMode'=>'human','controlOrigin'=>'manual']],true)==='human','Manual takeover remains absolute at rest');
}
ck(SalesPolicy::block([$customer,['rating'=>'S']],[])==='human','Linked account high blocks acquired active sales');
ck(SalesPolicy::block([['rating'=>'B','fusanheDoNotContact'=>true]],[],true)==='stopped','Optout remains absolute at rest');
ck(SalesPolicy::block([['rating'=>'B','fusanheSalesProfile'=>['paused'=>true]]],[],true)==='human','Customer pause remains absolute at rest');
ck(SalesPolicy::block([['rating'=>'B','emailAddressIsInvalid'=>true]],[])==='stopped','Invalid native email blocks');
$context=['rating'=>'B','mode'=>'acquisition','block'=>null,'profile'=>['email'=>'buyer@example.test','emailVerified'=>true,'emailSource'=>'verified public business source','timezone'=>'America/New_York','timezoneVerified'=>true,'timezoneSource'=>'confirmed location','business'=>'Bakery ingredients distributor','businessSource'=>'verified company website'],'contactPolicy'=>'allowed','products'=>[['productId'=>'p1','revision'=>3,'publicFacts'=>'用于烘焙食品。经审核可对外使用。']],'messages'=>[],'signatureApproved'=>true,'nowUtc'=>'2026-10-12 00:00:00','candidateTimes'=>[['local'=>'2026-10-13 11:00:00','utc'=>'2026-10-13 15:00:00']]];
ck(!SalesPolicy::requirements($context),'Complete source-backed facts are ready');
$missing=$context;$missing['profile']['timezoneVerified']=false;ck(in_array('客户时区及来源',SalesPolicy::requirements($missing),true),'Unknown timezone is not guessed');
$plan=['action'=>'send','reason'=>'相关烘焙业务','matches'=>[['productId'=>'p1','revision'=>3,'customerEvidence'=>'business','productFact'=>'用于烘焙食品。','reason'=>'业务相关']],'subject'=>'Ingredient inquiry','body'=>'Would you like product information?','localTime'=>'2026-10-13 11:00:00','dueUtc'=>'2026-10-13 15:00:00','timezone'=>'America/New_York','timeReason'=>'Initial business-hours assumption','validUntilUtc'=>'2026-10-13 21:00:00','nextEvaluationUtc'=>gmdate('Y-m-d H:i:s',time()+86400),'attachments'=>[]];
ck(SalesPlanner::validate($plan,$context)['action']==='send','Supported plan validates');
$high=$context;$high['rating']='A';ck(SalesPlanner::validate($plan,$high)['action']==='human','High active plan cannot emit send');
$rest=$high;$rest['mode']='reception';ck(SalesPlanner::validate($plan,$rest)['action']==='send','High rest reception remains eligible');
$stale=$plan;$stale['matches'][0]['revision']=2;rejected(fn()=>SalesPlanner::validate($stale,$context),'Stale product revision rejected');
$invented=$plan;$invented['matches'][0]['productFact']='ISO certificate';rejected(fn()=>SalesPlanner::validate($invented,$context),'Invented facts rejected');
$unknown=$plan;$unknown['matches'][0]['customerEvidence']='missingMessage';rejected(fn()=>SalesPlanner::validate($unknown,$context),'Unverified customer evidence rejected');
$attachments=$plan;$attachments['attachments']=['internal.pdf'];rejected(fn()=>SalesPlanner::validate($attachments,$context),'Attachments not enabled in v1');
$time=$plan;$time['dueUtc']='2026-10-13 16:00:00';rejected(fn()=>SalesPlanner::validate($time,$context),'Local UTC mismatch rejected');
rejected(fn()=>SalesPolicy::time('2026-11-01 01:30:00','America/New_York','2026-11-01 06:30:00',strtotime('2026-10-12 UTC')),'DST ambiguity does not produce a contact window');
$auto=$context;$auto['messages']=[['id'=>'auto','direction'=>'inbound','kind'=>'autoReply']];rejected(fn()=>SalesPlanner::validate($plan,$auto),'Never respond to auto replies');
ck(SalesPolicy::classify('accounts@zoho.com','Welcome to Zoho','')==='system','Zoho notices are not leads');
ck(SalesPolicy::classify('mailer-daemon@example.test','Delivery status notification','')==='bounce','Bounce recognized');
ck(SalesPolicy::classify('buyer@example.test','Hello','',['autoSubmitted'=>'auto-replied'])==='autoReply','Auto-Submitted recognized');
ck(SalesPolicy::classify('buyer@example.test','Product specs','Please send specs')==='customer','Customer mail recognized');
ck(SalesPolicy::refusal('Please unsubscribe me'),'Explicit refusal recognized');
ck(!SalesPolicy::refusal('Can you send specifications?'),'Normal inquiry is not an optout');
$changed=$context;$changed['products'][0]['revision']=4;ck(SalesPolicy::hash($context)!==SalesPolicy::hash($changed),'Product edits invalidate context');
$clock=$context;$clock['nowUtc']='2026-10-13 00:00:00';$clock['candidateTimes']=[];ck(SalesPolicy::hash($context)===SalesPolicy::hash($clock),'Unchanged customers do not call model every minute');
$atRest=$context;$atRest['receptionActive']=true;$atRest['receptionRevision']=10;$atWork=$atRest;$atWork['receptionActive']=false;$atWork['receptionRevision']=11;
ck(SalesPolicy::hash($atRest)===SalesPolicy::hash($atWork),'Company work boundary cannot regenerate acquired sales planned for customer time');
$atRest['mode']='reception';$atWork['mode']='reception';ck(SalesPolicy::hash($atRest)!==SalesPolicy::hash($atWork),'Rest intake still invalidates at company rest boundary or schedule change');
putenv('FUSANHE_TEXT_ENABLED=true');putenv('FUSANHE_TEXT_API_KEY=synthetic');putenv('FUSANHE_TEXT_API_BASE_URL=https://relay.example/v1');putenv('FUSANHE_TEXT_MODEL_GPT=gpt-6.1-sol');
$context['signature']="福三和食品\nfusanhe@example.test";$context['target']=['name'=>'Synthetic Buyer','kind'=>'person'];
$calls=0;$gateway=new TextGateway(function($url,$payload)use(&$calls,$plan,$context){$calls++;ck($payload['model']==='gpt-6.1-sol','Only user model');if($calls%2===0){$reviewInput=json_decode($payload['input'][1]['content'],true);ck($reviewInput['sender']['signatureApproved']===true&&$reviewInput['sender']['signature']===$context['signature'],'Independent reviewer receives approved sender identity');ck($reviewInput['target']['name']==='Synthetic Buyer','Reviewer can verify addressee against actual target');}$result=$calls%2?$plan:['approved'=>true,'reason'=>'Supported'];return [200,json_encode(['status'=>'completed','model'=>'gpt-6.1-sol','output'=>[['content'=>[['type'=>'output_text','text'=>json_encode($result)]]]]])];});
$result=(new SalesPlanner($gateway))->plan($context);ck($result['bodyReview']['approved']&&$calls===2,'Independent content review by same model');
putenv('FUSANHE_TEXT_MODEL_GPT=gpt-other');rejected(fn()=>(new SalesPlanner($gateway))->plan($context),'No model fallback');ck($calls===2,'Unsupported model never called');
putenv('FUSANHE_TEXT_MODEL_GPT=gpt-6.1-sol');
$noSearch=new TextGateway(fn()=>[200,json_encode(['status'=>'completed','model'=>'gpt-6.1-sol','output'=>[]])]);rejected(fn()=>$noSearch->salesResearch(['name'=>'Synthetic']),'Research must execute observable web search');
$withSearch=new TextGateway(fn()=>[200,json_encode(['status'=>'completed','model'=>'gpt-6.1-sol','output'=>[['type'=>'web_search_call','status'=>'completed','action'=>['sources'=>[['url'=>'https://example.test/contact','title'=>'Synthetic source']]]],['type'=>'message','content'=>[['type'=>'output_text','text'=>'Source-backed synthetic facts.']]]]])]);
ck($withSearch->salesResearch(['name'=>'Synthetic'])['sources'][0]['url']==='https://example.test/contact','Research source provenance retained');
$source=['fusanheSourceId'=>'xpoz:twitter:123','description'=>'公开账号资料：{"id":"123","name":"B&C Food Distributor","location":"Victoria BC"}'];
ck(SalesEnrichment::evidence($source)['profile']['location']==='Victoria BC','Original profile location reaches research');
$source['fusanheSourceId']='xpoz:twitter:456';ck(SalesEnrichment::evidence($source)['profile']===[],'Mismatched social identity is not accepted');
ck(SalesEnrichment::approvedUrl('https://www.example.test/contact/','example.test'),'Same official site canonical redirect allowed');
ck(!SalesEnrichment::approvedUrl('https://evil.test/contact','example.test'),'Off-site redirect prohibited');
ck(!SalesEnrichment::approvedUrl('http://example.test/contact','example.test'),'Redirect cannot downgrade HTTPS');
ck(!SalesEnrichment::approvedUrl('https://user:pass@example.test/','example.test'),'Credential-bearing redirect prohibited');
ck(SalesEnrichment::companyMailbox(['scope'=>'company','purpose'=>'general','sourceUrl'=>'https://example.test/contact']),'Public company business mailbox is eligible');
ck(!SalesEnrichment::companyMailbox(['scope'=>'company','purpose'=>'recruitment','sourceUrl'=>'https://example.test/contact']),'Recruitment address cannot become a sales recipient');
ck(!SalesEnrichment::companyMailbox(['scope'=>'company','purpose'=>'general','sourceUrl'=>'https://example.test/wholesale/company/employment/']),'Employment page is rejected even if model labels it general');
ck(!SalesEnrichment::companyMailbox(['scope'=>'company','sourceUrl'=>'https://example.test/contact']),'Unclassified department mailbox stays unverified');
echo "PASS $checks sales policy and planning assertions\n";
