<?php
require '/var/www/html/bootstrap.php';
use Espo\Custom\Tools\Fusanhe\{WebsiteSyncService,WebsitePolicy,WebsiteStore,SalesStore,ServiceKernel,SalesPolicy};
$app=new Espo\Core\Application();$app->setupSystemUser();$c=$app->getContainer();$em=$c->get('entityManager');$f=$c->get('injectableFactory');$kernel=new ServiceKernel($em);$service=$f->create(WebsiteSyncService::class);
$dir='/tmp/website-native-'.bin2hex(random_bytes(6));putenv('FUSANHE_WEBSITE_TEST_DIR='.$dir);mkdir($dir,0700);
$checks=0;function ck(bool $v,string $label){global $checks;if(!$v)throw new RuntimeException($label);$checks++;}function reject(callable $f,string $label){try{$f();}catch(Throwable){ck(true,$label);return;}throw new RuntimeException($label);}
$tx=$em->getTransactionManager();$tx->start();
try {
 $agent=$em->getRDBRepository('AutomationAgent')->where(['agentKey'=>WebsitePolicy::AGENT])->findOne()??$em->getNewEntity('AutomationAgent');$agent->set(['name'=>'Website synthetic contract','agentKey'=>WebsitePolicy::AGENT,'capabilities'=>['Website'],'mode'=>'real']);
 $key='contract-'.bin2hex(random_bytes(6));$event=['id'=>$key.'-customer','conversation'=>$key,'kind'=>'chat','role'=>'user','timestamp'=>time()-4000,'body'=>'Synthetic inquiry only','data'=>[]];
 $first=$service->sync(['site'=>WebsitePolicy::SITE,'events'=>[$event]],$agent);ck(!$first['results'][0]['deduplicated'],'First incoming event accepted');
 $again=$service->sync(['site'=>WebsitePolicy::SITE,'events'=>[$event]],$agent);ck($again['results'][0]['deduplicated'],'Retry is idempotent');
 $sequenced=$event;$sequenced['sequence']=0;$r=$service->sync(['site'=>WebsitePolicy::SITE,'events'=>[$sequenced]],$agent);$source=$em->getRDBRepository('ExternalMessage')->where(['id'=>$r['results'][0]['messageId']])->findOne();ck($source->get('sourceSequence')===1,'Sequence can be added without changing an older original message');
 ck($service->sync(['site'=>WebsitePolicy::SITE,'events'=>[$event]],$agent)['results'][0]['deduplicated'],'Retry from older source version remains idempotent');
 $changedSeq=$sequenced;$changedSeq['sequence']=5;reject(fn()=>$service->sync(['site'=>WebsitePolicy::SITE,'events'=>[$changedSeq]],$agent),'An existing source sequence cannot be changed');
 $conv=$em->getRDBRepository('ExternalConversation')->where(['id'=>$first['results'][0]['conversationId']])->findOne();ck(!$conv->get('leadId')&&$conv->get('needsManualMatch'),'Anonymous visitor never becomes guessed customer');
 $modified=$event;$modified['body']='changed';reject(fn()=>$service->sync(['site'=>WebsitePolicy::SITE,'events'=>[$modified]],$agent),'Changed content under same source ID rejected');
 $other=clone $agent;$other->set('agentKey','unrelated');reject(fn()=>$service->sync(['site'=>WebsitePolicy::SITE,'events'=>[]],$other),'Another automation credential cannot use site channel');
 reject(fn()=>$service->sync(['site'=>'https://another.test','events'=>[]],$agent),'Site is credential-bound');
 $invalid=$event;$invalid['role']='operator';reject(fn()=>WebsitePolicy::event($invalid),'Unrecognized sender role rejected');
 $bad=$event;$bad['timestamp']=time()+1000;reject(fn()=>WebsitePolicy::event($bad),'Future timestamps rejected');
 $form=$event;$form['id']=$key.'-form';$form['conversation']=$key.'-form';$form['kind']='form';$form['data']=['name'=>'Synthetic Buyer','email'=>'buyer@example.test','company'=>'Synthetic Company','country'=>'Synthetic Country','product'=>'Synthetic product','pack'=>'Synthetic pack'];
 $r=$service->sync(['site'=>WebsitePolicy::SITE,'events'=>[$form]],$agent);$m=$em->getRDBRepository('ExternalMessage')->where(['id'=>$r['results'][0]['messageId']])->findOne();$raw=SalesPolicy::data($m->get('rawPayload'));ck($raw['websiteEvent']['data']['pack']==='Synthetic pack'&&$raw['emailVerified']===false,'Submitted details retained without asserting verified email');
 $past=$event;$past['id']=$key.'-past-staff';$past['role']='human';$past['body']='Synthetic old staff reply';$service->sync(['site'=>WebsitePolicy::SITE,'events'=>[$past]],$agent);$beforeTakeover=$em->getRDBRepository('ExternalConversation')->where(['id'=>$conv->getId()])->findOne();ck($beforeTakeover->get('controlMode')==='aiAssist','Past staff reply does not invent a present takeover');
 $human=$event;$human['id']=$key.'-staff';$human['role']='human';$human['body']='Synthetic staff reply';$human['timestamp']++;$human['humanTakeover']=true;
 $r=$service->sync(['site'=>WebsitePolicy::SITE,'events'=>[$human]],$agent);$conv=$em->getRDBRepository('ExternalConversation')->where(['id'=>$conv->getId()])->findOne();ck($conv->get('controlMode')==='human'&&$conv->get('controlOrigin')==='manual','Website staff reply enforces manual takeover');
 $m=$em->getRDBRepository('ExternalMessage')->where(['id'=>$r['results'][0]['messageId']])->findOne();ck(!$m->get('automationKind')&&$m->get('direction')==='outbound','Actual staff message is imported without AI attribution');
 $receipt=$event;$receipt['id']=$key.'-false-ai';$receipt['role']='ai';$receipt['receiptId']='unissued';reject(fn()=>$service->sync(['site'=>WebsitePolicy::SITE,'events'=>[$receipt]],$agent),'Unissued reception reply cannot claim AI evidence');
 $stale=$service->sync(['site'=>WebsitePolicy::SITE,'events'=>[$event],'receptionEventId'=>$event['id']],$agent);ck($stale['reception']['status']==='awaiting_staff','Old/manual chat never triggers a new automatic reply');
 $another=$event;$another['id']=$key.'-anonymous-2';$another['conversation']=$key.'-visitor-2';$r=$service->sync(['site'=>WebsitePolicy::SITE,'events'=>[$another]],$agent);ck($r['results'][0]['conversationId']!==$conv->getId(),'Different anonymous browser sessions stay separate');
 $batch=$event;$batch['id']=$key.'-must-rollback';$batch['conversation']=$key.'-rollback';reject(fn()=>$service->sync(['site'=>WebsitePolicy::SITE,'events'=>[$batch,$receipt]],$agent),'Invalid outgoing receipt rolls back its batch');
 ck(!$em->getRDBRepository('ExternalMessage')->where(['externalId'=>'website:'.$batch['id']])->findOne(),'Rolled back batch is not acknowledged or partially persisted');
 echo "PASS $checks website native assertions; model/outbound not invoked, CRM writes rolled back\n";
}finally{$tx->rollback();putenv('FUSANHE_WEBSITE_TEST_DIR');foreach(glob($dir.'/*') as $p)unlink($p);rmdir($dir);}
