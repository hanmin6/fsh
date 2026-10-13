<?php
namespace Espo\Custom\Tools\Fusanhe;
use Espo\ORM\{Entity,EntityManager};
use Espo\Core\Exceptions\{BadRequest,Conflict,Forbidden};

final class WebsiteSyncService
{
    public function __construct(private EntityManager $em,private WorkflowService $workflow,private ServiceKernel $kernel,private ScheduledReceptionService $reception,private ReceptionReply $reply) {}
    public function sync(array $input,Entity $agent): array
    {
        if($agent->get('agentKey')!==WebsitePolicy::AGENT||!in_array('Website',SalesPolicy::data($agent->get('capabilities')),true)||$agent->get('mode')!=='real')throw new Forbidden('Website agent required.');
        if(($input['site']??'')!==WebsitePolicy::SITE)throw new Forbidden('Website account mismatch.');
        $events=$input['events']??null;if(!is_array($events)||!array_is_list($events)||count($events)>50)throw new BadRequest('Bounded website event list required.');
        $clean=array_map(fn($e)=>WebsitePolicy::event($e),$events);$lock=WebsiteStore::lock();$tx=$this->em->getTransactionManager();$started=false;
        try {
            $tx->start();$started=true;$out=[];
            foreach($clean as $event)$out[]=$this->import($event);
            $agent->set(['lastHeartbeatAt'=>$this->kernel->now(),'status'=>'online','lastError'=>null]);$this->kernel->save($agent);$tx->commit();$started=false;
            $reception=['status'=>'not_requested'];
            if(!empty($input['receptionEventId'])) {
                $requested=array_values(array_filter($clean,fn($e)=>$e['id']===$input['receptionEventId']&&$e['kind']==='chat'&&$e['role']==='user'));
                if(count($requested)!==1)throw new BadRequest('Reception must reference a submitted customer chat.');
                $reception=$this->receive($requested[0]);
            }
            WebsiteStore::status(['configured'=>true,'checkedAt'=>gmdate('Y-m-d H:i:s'),'site'=>WebsitePolicy::SITE,'events'=>count($out),'transport'=>'authenticated-push']);
            return ['results'=>$out,'reception'=>$reception];
        } finally {if($started)$tx->rollback();flock($lock,LOCK_UN);fclose($lock);}
    }
    private function import(array $e): array
    {
        $external='website:'.$e['id'];$existing=$this->em->getRDBRepository('ExternalMessage')->where(['externalId'=>$external])->findOne();
        if($existing) {
            $stored=SalesPolicy::data($existing->get('rawPayload'));$original=$stored['websiteEvent']??[];$a=$original;$b=$e;unset($a['sequence'],$b['sequence']);
            if($a!==$b||(isset($original['sequence'],$e['sequence'])&&$original['sequence']!==$e['sequence']))throw new Conflict('Website source ID changed contents.');
            if(isset($e['sequence'])&&!isset($original['sequence'])){$stored['websiteEvent']['sequence']=$e['sequence'];$existing->set(['rawPayload'=>$stored,'sourceSequence'=>$e['sequence']+1]);$this->kernel->save($existing);}
            return ['id'=>$e['id'],'deduplicated'=>true,'messageId'=>$existing->getId(),'conversationId'=>$existing->get('conversationId')];
        }
        $data=$e['data'];$sent=gmdate('Y-m-d H:i:s',$e['timestamp']);$conversationId='website:'.$e['conversation'];
        $channel=$this->em->getRDBRepository('ExternalChannel')->where(['type'=>'Website','accountHandle'=>WebsitePolicy::SITE])->findOne();
        $conv=$channel?$this->em->getRDBRepository('ExternalConversation')->where(['channelId'=>$channel->getId(),'externalId'=>$conversationId])->findOne():null;
        if($channel&&!$channel->get('enabled'))throw new Conflict('Website channel disabled.');
        if($e['role']==='user') {
            $previous=$conv?SalesPolicy::data($conv->getValueMap()):[];
            $result=$this->workflow->intake((object)['channelType'=>'Website','accountHandle'=>WebsitePolicy::SITE,'conversationExternalId'=>$conversationId,'messageExternalId'=>$external,
                'externalUserId'=>$e['kind']==='chat'?$e['conversation']:'','email'=>$data['email']??'','phone'=>mb_substr($data['phone']??'',0,100),'senderName'=>mb_substr($data['name']??'网站访客',0,255),'company'=>mb_substr($data['company']??'',0,255),
                'country'=>mb_substr($data['country']??'',0,100),'product'=>mb_substr($data['product']??'',0,255),'language'=>WebsitePolicy::language($e),'subject'=>$e['kind']==='form'?'官网询盘 · '.mb_substr($data['reqtype']??'general',0,100):'官网在线聊天',
                'body'=>$e['body'],'sentAt'=>$sent]);
            $message=$this->em->getRDBRepository('ExternalMessage')->where(['id'=>$result['messageId']])->findOne();$conv=$this->em->getRDBRepository('ExternalConversation')->where(['id'=>$result['conversationId']])->findOne();
            if(($previous['lastMessageAt']??'')>$sent)$conv->set(['lastMessageAt'=>$previous['lastMessageAt'],'lastMessagePreview'=>$previous['lastMessagePreview'],'status'=>$previous['status']]);
            if(($previous['lastInboundAt']??'')>$sent)$conv->set('lastInboundAt',$previous['lastInboundAt']);
        } else {
            if(!$conv)throw new Conflict('Customer chat must be imported before its replies.');
            $message=$this->kernel->create('ExternalMessage',['name'=>'OUT '.$external,'externalId'=>$external,'conversationId'=>$conv->getId(),'direction'=>'outbound',
                'senderName'=>$e['role']==='human'?'官网人工客服':($e['role']==='ai'?'官网 AI 客服':'官网系统'),'senderExternalId'=>'website:'.$e['role'],'body'=>$e['body'],'sentAt'=>$sent,'deliveryStatus'=>'sent',
                'contentHash'=>hash('sha256',$conv->getId().'|outbound|'.$external.'|'.$e['body'])]);
            if((string)$conv->get('lastOutboundAt')<=$sent)$conv->set('lastOutboundAt',$sent);
            if((string)$conv->get('lastMessageAt')<=$sent)$conv->set(['lastMessageAt'=>$sent,'lastMessagePreview'=>mb_substr(preg_replace('/\s+/u',' ',$e['body']),0,220),'status'=>'replied']);
            if($e['role']==='ai'&&$e['receiptId']) {
                $pending=WebsiteStore::receipt($e['receiptId']);
                if(!$pending||($pending['conversation']??'')!==$e['conversation']||($pending['body']??'')!==$e['body']||($pending['model']??'')!==SalesPolicy::MODEL)throw new Conflict('AI reception receipt does not match generated content.');
                $message->set('automationKind','scheduledReception');
            }
        }
        $message->set(['rawPayload'=>['source'=>'Website','websiteEvent'=>$e,'websiteRole'=>$e['role'],'emailVerified'=>false,'model'=>$e['receiptId']?SalesPolicy::MODEL:null],
            'sourceTimestampRaw'=>(string)$e['timestamp'],'timestampConfidence'=>'high','messageType'=>$e['kind']==='form'?'initialInquiry':'chat']);$this->kernel->save($message);
        if(isset($e['sequence'])){$message->set('sourceSequence',$e['sequence']+1);$this->kernel->save($message);}
        $conv->set('sourceUrl',$data['landing_page']??WebsitePolicy::SITE.($e['kind']==='form'?'/contact/':'/'));
        // A historical staff reply is evidence of past participation, not a current takeover.
        if($e['humanTakeover']||($e['role']==='human'&&$e['timestamp']>=time()-1800))$conv->set(['controlMode'=>'human','controlOrigin'=>'manual']);
        if($e['role']==='user'&&SalesPolicy::refusal($e['body']))$conv->set(['controlMode'=>'human','controlOrigin'=>'manual']);
        $this->kernel->save($conv);$this->kernel->audit('website.import','agent',WebsitePolicy::AGENT,'ExternalMessage',$message->getId(),'success',['sourceId'=>$e['id'],'kind'=>$e['kind'],'role'=>$e['role']]);
        return ['id'=>$e['id'],'deduplicated'=>false,'messageId'=>$message->getId(),'conversationId'=>$conv->getId()];
    }
    private function receive(array $e): array
    {
        $message=$this->em->getRDBRepository('ExternalMessage')->where(['externalId'=>'website:'.$e['id']])->findOne();
        $conv=$this->em->getRDBRepository('ExternalConversation')->where(['id'=>$message->get('conversationId')])->findOne();$config=ReceptionSettings::read();
        if(!$this->reception->allowed($conv,$config)||!$this->reception->fresh($message,$config)||SalesPolicy::refusal($e['body']))return ['status'=>'awaiting_staff'];
        $latest=$this->em->getRDBRepository('ExternalMessage')->where(['conversationId'=>$conv->getId(),'direction'=>'inbound'])->order('sentAt','DESC')->order('createdAt','DESC')->findOne();
        if($latest?->getId()!==$message->getId()||$this->em->getRDBRepository('ExternalMessage')->where(['conversationId'=>$conv->getId(),'direction'=>'outbound','sentAt>='=>$message->get('sentAt')])->findOne())return ['status'=>'superseded'];
        $receiptId='website-reception:'.$e['id'];$saved=WebsiteStore::receipt($receiptId);
        if($saved&&$saved['expiresAt']>time())return ['status'=>'reply','receiptId'=>$receiptId,'body'=>$saved['body'],'model'=>$saved['model']];
        try{$answer=$this->reply->generate($e['body'],WebsitePolicy::language($e));}catch(\Throwable){return ['status'=>'awaiting_staff'];}
        $fresh=$this->em->getRDBRepository('ExternalConversation')->where(['id'=>$conv->getId()])->findOne();$now=ReceptionSettings::read();
        if($config['revision']!==$now['revision']||!$this->reception->allowed($fresh,$now)||!$this->reception->fresh($message,$now))return ['status'=>'awaiting_staff'];
        WebsiteStore::receipt($receiptId,['conversation'=>$e['conversation'],'body'=>$answer['text'],'model'=>$answer['model'],'expiresAt'=>time()+1800,'sourceMessageId'=>$message->getId()]);
        return ['status'=>'reply','receiptId'=>$receiptId,'body'=>$answer['text'],'model'=>$answer['model']];
    }
}
