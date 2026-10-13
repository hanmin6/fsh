<?php
/** Run inside EspoCRM. All CRM writes roll back; transport and product approval are isolated. */
require '/var/www/html/bootstrap.php';
use Espo\Custom\Tools\Fusanhe\{SalesStore,SalesPolicy,SalesPlanner,SalesService,SalesMailSender,ServiceKernel,TextGateway,SalesEnrichment};
use Espo\Core\Field\DateTime;
use Espo\Entities\Email;
$app=new Espo\Core\Application();$app->setupSystemUser();$c=$app->getContainer();$em=$c->get('entityManager');$factory=$c->get('injectableFactory');$kernel=new ServiceKernel($em);
$dir='/tmp/sales-native-'.bin2hex(random_bytes(6));putenv('FUSANHE_SALES_TEST_DIR='.$dir);mkdir($dir,0700);
$checks=0;function ck(bool $ok,string $label): void {global $checks;if (!$ok)throw new RuntimeException($label);$checks++;}
$tx=$em->getTransactionManager();$tx->start();
try {
 $settings=SalesStore::defaults();$settings['enabled']=false;$settings['signatureApproved']=true;SalesStore::mutate('settings',fn()=> $settings);
 $product=$em->getRDBRepository('FusanheProduct')->findOne();$pid=$product->getId();
 SalesStore::card($pid,['revision'=>0,'name'=>'Synthetic product','nameEn'=>'Synthetic','applications'=>'Synthetic bakery','publicFacts'=>'仅合同测试中的产品事实。','source'=>'synthetic evidence','validUntil'=>gmdate('Y-m-d',time()+86400*30),'status'=>'approved'],'synthetic-admin');
 $name='SYNTHETIC '.bin2hex(random_bytes(5));
 $lead=$em->getNewEntity('Lead');$lead->set(['name'=>$name,'firstName'=>$name,'lastName'=>'Contract','rating'=>'B','ratingSource'=>'manual','fusanheSourceSystem'=>'muse','fusanheSourceId'=>$name,'aiRatingStatus'=>'completed','fusanheSalesEnrolled'=>true,'fusanheContactPolicy'=>'allowed',
  'fusanheSalesProfile'=>['email'=>'buyer@example.test','emailVerified'=>true,'emailSource'=>'synthetic','timezone'=>'America/New_York','timezoneVerified'=>true,'timezoneSource'=>'synthetic location','business'=>'Synthetic bakery','businessSource'=>'synthetic evidence','paused'=>false]]);$kernel->save($lead,['fusanheRating'=>true]);
 $calls=0;$gateway=new TextGateway(function($url,$payload)use(&$calls,$pid){$calls++;$input=json_decode($payload['input'][1]['content'],true);
  if (isset($input['candidateTimes'])) {$t=$input['candidateTimes'][0];$out=['action'=>'send','reason'=>'Synthetic plan','matches'=>[['productId'=>$pid,'revision'=>1,'customerEvidence'=>'business','productFact'=>'仅合同测试中的产品事实。','reason'=>'Synthetic evidence']],'subject'=>'Synthetic only','body'=>'Which ingredient specifications do you need?','localTime'=>$t['local'],'dueUtc'=>$t['utc'],'timezone'=>$input['profile']['timezone'],'timeReason'=>'Synthetic initial assumption','validUntilUtc'=>gmdate('Y-m-d H:i:s',strtotime($t['utc'].' UTC')+3600),'nextEvaluationUtc'=>gmdate('Y-m-d H:i:s',time()+86400*4),'attachments'=>[]];}
  else $out=['approved'=>true,'reason'=>'Synthetic evidence'];
  return [200,json_encode(['status'=>'completed','model'=>'gpt-6.1-sol','output'=>[['content'=>[['type'=>'output_text','text'=>json_encode($out)]]]]])];});
 $submissions=0;$sender=new SalesMailSender($em,$factory,$kernel,function(Email $email)use(&$submissions){$submissions++;$email->setStatus('Sent')->setDateSent(DateTime::createNow());});
 $service=new SalesService($em,$kernel,new SalesPlanner($gateway),$sender);
 $result=$service->run('Lead',$lead->getId(),true);ck($result['status']==='preview','Complete acquired B previews before activation');ck($calls===2,'One planning and content review');
 $reviewed=SalesPolicy::data($result['plan']);$settings['enabled']=true;$settings['revision']=1;$settings['activationEpoch']='synthetic-epoch';SalesStore::mutate('settings',fn()=> $settings);
 $result=$service->activatePreview($result['id'],(int)$result['generation']);ck($result['status']==='scheduled','Reviewed pilot becomes scheduled');ck(SalesPolicy::data($result['plan'])===$reviewed&&$calls===2,'Activation preserves reviewed content and time without replanning');
 $restBoundaryRow=$em->getRDBRepository('FusanheSalesPlan')->where(['id'=>$result['id']])->findOne();$oldRestContext=SalesPolicy::data($restBoundaryRow->get('context'));$oldRestContext['receptionActive']=!$oldRestContext['receptionActive'];$oldRestContext['receptionRevision']++;
 $restBoundaryRow->set(['context'=>$oldRestContext,'contextHash'=>SalesPolicy::hash($oldRestContext)]);$kernel->save($restBoundaryRow);
 $same=$service->run('Lead',$lead->getId());ck($calls===2&&$same['generation']===1,'Unchanged candidate not replanned');
 ck($same['status']==='scheduled'&&SalesPolicy::data($same['plan'])===$reviewed,'Crossing company rest boundary preserves exact scheduled reviewed mail');
 $row=$em->getRDBRepository('FusanheSalesPlan')->where(['id'=>$result['id']])->findOne();$context=$service->context('Lead',$lead->getId());
 $row->set('dueAt',gmdate('Y-m-d H:i:s',time()-1));$kernel->save($row);
 ck($service->sendBlock($row,$context,$settings)===null,'Due authorized plan allowed');
 $high=$context;$high['rating']='A';ck($service->sendBlock($row,$high,$settings)!==null,'Promotion checked at final send boundary');
 $human=$context;$human['block']='human';ck($service->sendBlock($row,$human,$settings)!==null,'Manual takeover blocks');
 $pendingRating=$context;$pendingRating['ratingReady']=false;ck($service->sendBlock($row,$pendingRating,$settings)!==null,'Acquired sales waits for new-reply rating review');
 $revised=$context;$revised['products'][0]['revision']=2;ck($service->sendBlock($row,$revised,$settings)!==null,'Withdrawn or edited facts revoke');
 $reply=$context;$reply['messages'][]=['id'=>'new','direction'=>'inbound','body'=>'New reply'];ck($service->sendBlock($row,$reply,$settings)!==null,'New reply revokes stale plan');
 $old=$settings;$old['activationEpoch']='previous';ck($service->sendBlock($row,$context,$old)!==null,'Old authorization never executes');
 $platform=$context;$platform['mode']='platform';ck($service->sendBlock($row,$platform,$settings)!==null,'Other platform never enters all-day active sales');
 $rest=$context;$rest['rating']='A';$rest['mode']='reception';$rest['receptionActive']=true;$rest['sourceMessageId']='synthetic-source';$row->set('contextHash',SalesPolicy::hash($rest));
 ck($service->sendBlock($row,$rest,$settings)===null,'High rest-time intake allowed');$rest['receptionActive']=false;ck($service->sendBlock($row,$rest,$settings)!==null,'Rest boundary rechecked');
 $rest['receptionActive']=true;$rest['ratingReady']=false;$row->set('contextHash',SalesPolicy::hash($rest));ck($service->sendBlock($row,$rest,$settings)===null,'Rest intake still takes priority during rating review');
 $row->set('contextHash',SalesPolicy::hash($context));$kernel->save($row);
 $r=$service->tick();ck($submissions===1,'Native SMTP boundary exercised with injected transport');
 $service->tick();ck($submissions===1,'Repeated minute tick never resends');
 $row=$em->getRDBRepository('FusanheSalesPlan')->where(['id'=>$row->getId()])->findOne();ck($row->get('nativeEmailId')!==null,'Native email identity retained');
 $message=$em->getEntityById('ExternalMessage',$row->get('ownMessageId'));ck(!empty(((array)$message->get('rawPayload'))['salesPlanSnapshot']),'Immutable source and product snapshot retained');
 $email=$em->getEntityById('Email',$row->get('nativeEmailId'));ck($email->get('status')==='Sent'&&in_array('buyer@example.test',$email->getToAddressList(),true),'Native sender and recipient shape');
 $row->set(['status'=>'uncertain','contextHash'=>null]);$kernel->save($row);$service->run('Lead',$lead->getId(),true);$service->tick();ck($submissions===1,'Uncertain outcome never retried');
 $service->receive($message,$email,['references'=>$email->getMessageId().' '.$email->getMessageId(),'inReplyTo'=>$email->getMessageId()]);
 $resolved=$em->getRDBRepository('FusanheSalesPlan')->where(['id'=>$row->getId()])->findOne();ck($resolved->get('status')==='submitted','Sent-folder proof reconciles uncertain outcome');
 $count=$resolved->get('unansweredCount');$service->receive($message,$email,['references'=>$email->getMessageId()]);$resolved=$em->getRDBRepository('FusanheSalesPlan')->where(['id'=>$row->getId()])->findOne();ck($resolved->get('unansweredCount')===$count,'Duplicate RFC references and sync do not duplicate outcome');
 $reply=$kernel->create('Email',['name'=>'Stop contact','from'=>'buyer@example.test','to'=>'fusanhe@fshfoodingredients.com','body'=>'Please unsubscribe me','bodyPlain'=>'Please unsubscribe me','isHtml'=>false,'status'=>'Archived','messageId'=>'<synthetic.reply@example.test>']);
 $incoming=$kernel->create('ExternalMessage',['name'=>'Synthetic inbound','conversationId'=>$message->get('conversationId'),'externalId'=>'synthetic:'.$name,'direction'=>'inbound','body'=>'Please unsubscribe me','sentAt'=>gmdate('Y-m-d H:i:s'),'contentHash'=>hash('sha256',$name)]);
 $service->receive($incoming,$reply,['references'=>$email->getMessageId()]);
 $stopped=$em->getRDBRepository('Lead')->where(['id'=>$lead->getId()])->findOne();ck($stopped->get('fusanheContactPolicy')==='optedOut','Refusal updates shared customer state immediately');
 ck($stopped->get('aiRatingStatus')==='completed','Manual rating remains authoritative on reply');
 $stopped->set(['fusanheSalesProfile'=>[],'website'=>'https://example.test']);$kernel->save($stopped);
 $researchGateway=new TextGateway(function($url,$payload){
  if(isset($payload['tools']))return [200,json_encode(['status'=>'completed','model'=>'gpt-6.1-sol','output'=>[['type'=>'web_search_call','status'=>'completed','action'=>['sources'=>[['url'=>'https://example.test/contact','title'=>'Synthetic official source']]]],['content'=>[['type'=>'output_text','text'=>'Synthetic official evidence']]]]])];
  return [200,json_encode(['status'=>'completed','model'=>'gpt-6.1-sol','output'=>[['content'=>[['type'=>'output_text','text'=>json_encode(['identityConfirmed'=>true,'email'=>['address'=>'guessed@example.test','sourceUrl'=>'https://example.test/contact','quote'=>'This address was not published','personMatched'=>true],'timezone'=>['iana'=>'America/New_York','sourceUrl'=>'https://example.test/contact','quote'=>'Verified location in New York'],'business'=>['summary'=>'Synthetic bakery','sourceUrl'=>'https://example.test/contact','quote'=>'We distribute bakery ingredients']])]]]]])];});
 $enrich=new SalesEnrichment($em,$researchGateway,$kernel,fn()=> 'Verified location in New York. We distribute bakery ingredients.');$enrich->run('Lead',$lead->getId());
 $enriched=$em->getRDBRepository('Lead')->where(['id'=>$lead->getId()])->findOne();$p=SalesPolicy::data($enriched->get('fusanheSalesProfile'));ck(empty($p['email']),'Unpublished email cannot be guessed into CRM');ck(($p['business']??'')==='Synthetic bakery'&&($p['timezone']??'')==='America/New_York','Only fetched exact-source facts are accepted');
 $enriched->set(['ratingSource'=>'auto','aiRatingStatus'=>'completed','fusanheDoNotContact'=>false,'fusanheContactPolicy'=>'allowed']);$kernel->save($enriched,['fusanheRating'=>true]);
 $newReply=$kernel->create('Email',['name'=>'Product inquiry','from'=>'buyer@example.test','to'=>'fusanhe@fshfoodingredients.com','body'=>'Could you share specifications?','bodyPlain'=>'Could you share specifications?','isHtml'=>false,'status'=>'Archived','messageId'=>'<synthetic.new.reply@example.test>']);
 $newMessage=$kernel->create('ExternalMessage',['name'=>'Synthetic inquiry','conversationId'=>$message->get('conversationId'),'externalId'=>'synthetic:new:'.$name,'direction'=>'inbound','body'=>'Could you share specifications?','sentAt'=>gmdate('Y-m-d H:i:s'),'contentHash'=>hash('sha256','new'.$name)]);
 $service->receive($newMessage,$newReply,['references'=>$email->getMessageId()]);$fresh=$em->getRDBRepository('Lead')->where(['id'=>$lead->getId()])->findOne();ck($fresh->get('aiRatingStatus')==='pending','Real reply queues fresh AI rating before acquired active sales');
 $companyLead=$em->getNewEntity('Lead');$companyLead->set(['name'=>'Synthetic Food Distributor','firstName'=>'Synthetic Food Distributor','rating'=>'B','ratingSource'=>'manual','fusanheSourceSystem'=>'muse','fusanheSourceId'=>'xpoz:twitter:123456789','description'=>'公开账号资料：{"id":"123456789","name":"Synthetic Food Distributor","location":"Victoria BC"}','fusanheContactPolicy'=>'allowed']);$kernel->save($companyLead,['fusanheRating'=>true]);
 $companyGateway=new TextGateway(function($url,$payload){
  if(isset($payload['tools'])) { $input=json_decode($payload['input'][1]['content'],true);ck($input['originalEvidence']['profile']['location']==='Victoria BC','Company source anchors are not omitted');return [200,json_encode(['status'=>'completed','model'=>'gpt-6.1-sol','output'=>[['type'=>'web_search_call','status'=>'completed','action'=>['sources'=>[['url'=>'https://example.test/contact','title'=>'Synthetic official site']]]],['content'=>[['type'=>'output_text','text'=>'Synthetic corporate evidence']]]]])]; }
  return [200,json_encode(['status'=>'completed','model'=>'gpt-6.1-sol','output'=>[['content'=>[['type'=>'output_text','text'=>json_encode(['identityConfirmed'=>true,'officialWebsite'=>'https://example.test','email'=>['address'=>'info@example.test','sourceUrl'=>'https://example.test/contact','quote'=>'Contact us at info@example.test','scope'=>'company','purpose'=>'general','personMatched'=>false],'business'=>['summary'=>'Synthetic bakery distributor','sourceUrl'=>'https://example.test/contact','quote'=>'We distribute bakery ingredients']])]]]]])];});
 (new SalesEnrichment($em,$companyGateway,$kernel,fn()=> 'Contact us at info@example.test. We distribute bakery ingredients.'))->run('Lead',$companyLead->getId());
 $corporate=$em->getRDBRepository('Lead')->where(['id'=>$companyLead->getId()])->findOne();$corporateProfile=SalesPolicy::data($corporate->get('fusanheSalesProfile'));ck(($corporateProfile['emailVerified']??false)===true&&$corporateProfile['contactScope']==='company','Confirmed company mailbox is distinct from a personal mailbox');
 echo "PASS $checks native workflow assertions; SMTP mocked, CRM transaction rolled back\n";
} finally {$tx->rollback();putenv('FUSANHE_SALES_TEST_DIR');foreach(glob($dir.'/*') as $f)unlink($f);rmdir($dir);}
