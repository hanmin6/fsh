<?php
namespace Espo\Custom\Tools\Fusanhe;

use DateTimeImmutable;
use DateTimeZone;
use Espo\Core\Exceptions\BadRequest;
use Espo\Core\Exceptions\Conflict;
use Espo\Core\Exceptions\NotFound;
use Espo\ORM\Entity;
use Espo\ORM\EntityManager;
use Espo\Entities\User;
use stdClass;

final class WorkflowService
{
    public function __construct(private EntityManager $em, private AiProvider $aiProvider) {}

    public function intake(stdClass $input): array
    {
        $channelType = (string) ($input->channelType ?? 'Alibaba');
        $externalId = trim((string) ($input->conversationExternalId ?? ''));
        $messageId = trim((string) ($input->messageExternalId ?? ''));
        $body = trim((string) ($input->body ?? ''));
        if ($externalId === '' || $messageId === '' || $body === '') throw new BadRequest('conversationExternalId, messageExternalId and body are required.');

        $channel = $this->repo('ExternalChannel')->where(['type' => $channelType])->findOne();
        if (!$channel) {
            $channel = $this->create('ExternalChannel', ['name' => $channelType . '（模拟）','type' => $channelType,'enabled' => true,'connectionStatus' => 'healthy']);
        }
        $conversation = $this->repo('ExternalConversation')->where(['channelId' => $channel->getId(), 'externalId' => $externalId])->findOne();
        $createdLead = false;
        if (!$conversation) {
            $customer = $this->matchOrCreateCustomer($input, $channel->getId());
            $createdLead = $customer['created'];
            $conversation = $this->create('ExternalConversation', [
                'name' => (string) ($input->subject ?? ('询盘 ' . $externalId)), 'subject' => (string) ($input->subject ?? ''),
                'channelId' => $channel->getId(), 'externalId' => $externalId, 'externalUserId' => (string) ($input->externalUserId ?? ''),
                ...$customer['links'], 'country' => (string) ($input->country ?? ''), 'language' => (string) ($input->language ?? 'en'),
                'product' => (string) ($input->product ?? ''), 'status' => 'new', 'needsManualMatch' => $lead['created'], 'unreadCount' => 0,
            ]);
        }
        $hash = hash('sha256', $conversation->getId() . '|inbound|' . $messageId . '|' . $body);
        $existing = $this->repo('ExternalMessage')->where(['conversationId' => $conversation->getId(), 'contentHash' => $hash])->findOne();
        if ($existing) return ['deduplicated' => true, 'conversationId' => $conversation->getId(), 'messageId' => $existing->getId(), 'createdLead' => false];
        $sentAt = (string) ($input->sentAt ?? $this->now());
        $message = $this->create('ExternalMessage', [
            'name' => 'IN ' . $messageId, 'conversationId' => $conversation->getId(), 'externalId' => $messageId, 'direction' => 'inbound',
            'senderName' => (string) ($input->senderName ?? 'Customer'), 'senderExternalId' => (string) ($input->externalUserId ?? ''),
            'sentAt' => $sentAt, 'body' => $body, 'deliveryStatus' => 'received', 'contentHash' => $hash,
            'rawPayload' => json_decode(json_encode($input), true),
        ]);
        $conversation->set(['lastMessageAt' => $sentAt, 'lastInboundAt' => $sentAt, 'lastMessagePreview' => mb_substr(preg_replace('/\s+/', ' ', $body), 0, 220), 'waitingMinutes' => 0, 'unreadCount' => ((int)$conversation->get('unreadCount')) + 1, 'status' => 'pending']);
        $this->em->saveEntity($conversation);
        $this->audit('message.intake','connector',$channelType,'ExternalMessage',$message->getId(),'success',['deduplicated'=>false]);
        return ['deduplicated' => false, 'conversationId' => $conversation->getId(), 'messageId' => $message->getId(), 'createdLead' => $createdLead];
    }

    public function generateDraft(string $conversationId): array
    {
        $conversation = $this->requireEntity('ExternalConversation',$conversationId);
        $message = $this->repo('ExternalMessage')->where(['conversationId'=>$conversationId,'direction'=>'inbound'])->order('sentAt','DESC')->findOne();
        if (!$message) throw new Conflict('No inbound message available.');
        $docs = $this->repo('KnowledgeDocument')->where(['approvalStatus'=>'approved'])->limit(5)->find();
        $knowledge=[];
        foreach ($docs as $doc) $knowledge[]=['id'=>$doc->getId(),'title'=>$doc->get('name'),'text'=>mb_substr((string)$doc->get('extractedText'),0,3000)];
        $history=[];
        foreach($this->repo('ExternalMessage')->where(['conversationId'=>$conversationId])->order('sentAt','ASC')->limit(20)->find() as $item) $history[]=['direction'=>$item->get('direction'),'body'=>$item->get('body'),'sentAt'=>$item->get('sentAt')];
        $result=$this->aiProvider->generate([
            'country'=>$conversation->get('country'),'language'=>$conversation->get('language'),'product'=>$conversation->get('product'),
            'message'=>$message->get('body'),'history'=>$history,'opportunityStage'=>null,'companyRules'=>['Do not promise price, MOQ, lead time, certification, payment, discounts, quality or compensation without approved evidence.'],'knowledge'=>$knowledge,
        ]);
        $draft=$this->create('AIReplyDraft',[
            'name'=>'AI 草稿 '.date('Y-m-d H:i'),'conversationId'=>$conversationId,'sourceMessageId'=>$message->getId(),
            'draftText'=>$result['draftText'],'intent'=>$result['intent'],'summaryZh'=>$result['summaryZh'],'suggestedLanguage'=>$result['suggestedLanguage'],
            'riskLevel'=>$result['riskLevel'],'confidence'=>$result['confidence'],'missingInformation'=>$result['missingInformation'],
            'citedKnowledge'=>$result['citedKnowledge'],'modelProvider'=>$result['provider'],'modelName'=>$result['model'],'promptVersion'=>'mvp-v1','status'=>'generated',
        ]);
        $conversation->set('status','waitingApproval'); $this->em->saveEntity($conversation);
        $this->audit('draft.generated','user','current','AIReplyDraft',$draft->getId(),'success',['provider'=>$result['provider']]);
        return ['draftId'=>$draft->getId()] + $result;
    }

    public function approve(string $draftId, User $user, ?string $editedText): array
    {
        $draft=$this->requireEntity('AIReplyDraft',$draftId);
        if (!in_array($draft->get('status'),['generated','edited'],true)) throw new Conflict('Draft is not approvable.');
        if ($editedText !== null && trim($editedText)!=='' && trim($editedText) !== trim((string) $draft->get('draftText'))) $draft->set(['draftText'=>trim($editedText),'status'=>'edited','wasEdited'=>true]);
        $key=hash('sha256',$draft->getId().'|'.$draft->get('draftText'));
        $task=$this->repo('OutboundTask')->where(['idempotencyKey'=>$key])->findOne();
        $deduplicated = (bool) $task;
        $conversation=$this->requireEntity('ExternalConversation',(string)$draft->get('conversationId'));
        if (!$task) {
            $task=$this->create('OutboundTask',[
                'name'=>'发送任务 '.substr($key,0,10),'conversationId'=>$conversation->getId(),'replyDraftId'=>$draft->getId(),
                'channelId'=>$conversation->get('channelId'),'status'=>'pending','idempotencyKey'=>$key,'payload'=>['body'=>$draft->get('draftText')],
            ]);
        }
        $draft->set(['status'=>'approved','approvedById'=>$user->getId(),'approvedAt'=>$this->now()]); $this->em->saveEntity($draft);
        $conversation->set('status','readyToSend'); $this->em->saveEntity($conversation);
        $this->audit('draft.approved','user',$user->getId(),'OutboundTask',$task->getId(),'success',['idempotencyKey'=>$key]);
        return ['taskId'=>$task->getId(),'idempotencyKey'=>$key,'deduplicated'=>$deduplicated];
    }

    public function registerAgent(stdClass $input): array
    {
        $key=trim((string)($input->agentKey??'')); if ($key==='') throw new BadRequest('agentKey is required.');
        $agent=$this->repo('AutomationAgent')->where(['agentKey'=>$key])->findOne();
        if(!$agent) $agent=$this->create('AutomationAgent',['name'=>(string)($input->name??$key),'agentKey'=>$key]);
        $agent->set(['status'=>'online','lastHeartbeatAt'=>$this->now(),'capabilities'=>(array)($input->capabilities??[]),'lastError'=>null]); $this->em->saveEntity($agent);
        $this->audit('agent.register','agent',$key,'AutomationAgent',$agent->getId());
        return ['agentId'=>$agent->getId(),'status'=>'online'];
    }

    public function heartbeat(stdClass $input): array
    {
        $key=(string)($input->agentKey??''); $agent=$this->repo('AutomationAgent')->where(['agentKey'=>$key])->findOne();
        if(!$agent) throw new NotFound('Agent not registered.');
        $status=(string)($input->status??'online');
        $agent->set(['status'=>$status,'lastHeartbeatAt'=>$this->now(),'lastError'=>$input->lastError??null]); $this->em->saveEntity($agent);
        $this->audit('agent.heartbeat','agent',$key,'AutomationAgent',$agent->getId(),$status==='online'?'success':'failure',['status'=>$status]);
        return ['ok'=>true];
    }

    public function claim(stdClass $input): array
    {
        if (filter_var(getenv('FUSANHE_OUTBOUND_PAUSED') ?: 'true', FILTER_VALIDATE_BOOLEAN)) return ['task'=>null,'paused'=>true];
        $key=(string)($input->agentKey??''); if($key==='') throw new BadRequest('agentKey is required.');
        $tx=$this->em->getTransactionManager(); $tx->start();
        try {
            $now=$this->now();
            foreach($this->repo('OutboundTask')->where(['status'=>'claimed','claimExpiresAt<'=>$now])->find() as $expired){$expired->set(['status'=>'pending','claimedBy'=>null,'claimedAt'=>null,'claimExpiresAt'=>null]);$this->em->saveEntity($expired);}
            $task=$this->repo('OutboundTask')->forUpdate()->where(['status'=>'pending'])->order('createdAt','ASC')->findOne();
            if(!$task){$tx->commit(); return ['task'=>null,'paused'=>false];}
            $active=$this->repo('OutboundTask')->where(['conversationId'=>$task->get('conversationId'),'status'=>['claimed','sending']])->findOne();
            if($active){$tx->commit(); return ['task'=>null,'paused'=>false];}
            $task->set(['status'=>'claimed','claimedBy'=>$key,'claimedAt'=>$now,'claimExpiresAt'=>(new DateTimeImmutable('+5 minutes'))->setTimezone(new DateTimeZone('UTC'))->format('Y-m-d H:i:s')]);
            $this->em->saveEntity($task); $tx->commit();
            $this->audit('task.claimed','agent',$key,'OutboundTask',$task->getId());
            return ['paused'=>false,'task'=>$this->taskPayload($task)];
        } catch (\Throwable $e) { $tx->rollback(); throw $e; }
    }

    public function markSending(string $id, stdClass $input): array
    {
        $task=$this->ownedTask($id,(string)($input->agentKey??''));
        if($task->get('status')!=='claimed') throw new Conflict('Task must be claimed first.');
        $task->set('status','sending'); $this->em->saveEntity($task); $this->syncConversation($task,'sending');
        $this->audit('task.sending','agent',(string)$task->get('claimedBy'),'OutboundTask',$id); return ['ok'=>true];
    }

    public function reportResult(string $id, stdClass $input): array
    {
        $task=$this->ownedTask($id,(string)($input->agentKey??''));
        if(!in_array($task->get('status'),['claimed','sending'],true)) throw new Conflict('Task is not active.');
        $success=(bool)($input->success??false);
        if($success){
            $task->set(['status'=>'sent','platformMessageId'=>(string)($input->platformMessageId??''),'completedAt'=>$this->now(),'errorMessage'=>null]);
            $draft=$this->requireEntity('AIReplyDraft',(string)$task->get('replyDraftId')); $draft->set('status','sent'); $this->em->saveEntity($draft);
            $conv=$this->requireEntity('ExternalConversation',(string)$task->get('conversationId'));
            $body=(string)$draft->get('draftText'); $hash=hash('sha256',$conv->getId().'|outbound|'.$task->get('idempotencyKey'));
            if(!$this->repo('ExternalMessage')->where(['conversationId'=>$conv->getId(),'contentHash'=>$hash])->findOne()) {
                $this->create('ExternalMessage',['name'=>'OUT '.substr($hash,0,8),'conversationId'=>$conv->getId(),'externalId'=>(string)($input->platformMessageId??$task->getId()),'direction'=>'outbound','senderName'=>'福三和','sentAt'=>$this->now(),'body'=>$body,'deliveryStatus'=>'sent','contentHash'=>$hash]);
            }
            $conv->set(['status'=>'sent','lastOutboundAt'=>$this->now(),'lastMessageAt'=>$this->now(),'lastMessagePreview'=>mb_substr(preg_replace('/\s+/',' ',$body),0,220),'waitingMinutes'=>null,'unreadCount'=>0]);
            if($conv->get('lastInboundAt')) $conv->set('firstResponseMinutes',max(0,(int)round((time()-strtotime((string)$conv->get('lastInboundAt')))/60)));
            $this->em->saveEntity($conv);
        } else {
            $retries=((int)$task->get('retryCount'))+1; $task->set(['retryCount'=>$retries,'status'=>$retries<3?'pending':'failed','errorMessage'=>(string)($input->errorMessage??'Unknown send error'),'claimedBy'=>null,'claimExpiresAt'=>null]);
            $this->syncConversation($task,$retries<3?'readyToSend':'failed');
        }
        $this->em->saveEntity($task); $this->audit('task.result','agent',(string)($input->agentKey??''),'OutboundTask',$id,$success?'success':'failure',['platformMessageId'=>$input->platformMessageId??null]);
        return ['ok'=>true,'status'=>$task->get('status')];
    }

    public function dashboard(): array
    {
        $today=date('Y-m-d 00:00:00');
        $count=fn(string $type,array $where=[])=>$this->repo($type)->where($where)->count();
        $conversations=$this->repo('ExternalConversation')->where(['createdAt>='=>$today])->find(); $channels=[];$byAssignedUser=[];
        foreach($conversations as $c){$channel=$this->em->getEntityById('ExternalChannel',(string)$c->get('channelId'));$k=$channel?(string)$channel->get('type'):'Unknown';$channels[$k]=($channels[$k]??0)+1;$owner=(string)($c->get('assignedUserName')?:'未分配');$byAssignedUser[$owner]=($byAssignedUser[$owner]??0)+1;}
        $open=$this->repo('ExternalConversation')->where(['status'=>['new','pending','drafted','waitingApproval']])->find();$slaBreached=0;
        foreach($open as $c){$waiting=$c->get('lastInboundAt')?max(0,(int)floor((time()-strtotime((string)$c->get('lastInboundAt')))/60)):null;$breached=$waiting!==null&&$waiting>=120;if((bool)$c->get('slaBreached')!==$breached||$c->get('waitingMinutes')!==$waiting){$c->set(['slaBreached'=>$breached,'waitingMinutes'=>$waiting]);$this->em->saveEntity($c);}if($breached)$slaBreached++;}
        $responded=$this->repo('ExternalConversation')->where(['firstResponseMinutes!='=>null])->find(); $sum=0;$n=0;
        foreach($responded as $c){$sum+=(int)$c->get('firstResponseMinutes');$n++;}
        $draftTotal=$count('AIReplyDraft'); $edited=$count('AIReplyDraft',['wasEdited'=>true]); $taskTotal=$count('OutboundTask'); $sent=$count('OutboundTask',['status'=>'sent']);
        return ['todayInquiries'=>count($conversations),'byChannel'=>$channels,'byAssignedUser'=>$byAssignedUser,'unassigned'=>$count('ExternalConversation',['assignedUserId'=>null]),'waitingReply'=>$count('ExternalConversation',['status'=>['new','pending']]),'waitingApproval'=>$count('ExternalConversation',['status'=>'waitingApproval']),'slaBreached'=>$slaBreached,'averageFirstResponseMinutes'=>$n?round($sum/$n,1):null,'aiDrafts'=>$draftTotal,'humanEditRate'=>$draftTotal?round($edited/$draftTotal,3):0,'sendSuccessRate'=>$taskTotal?round($sent/$taskTotal,3):0,'failedTasks'=>$count('OutboundTask',['status'=>'failed'])];
    }

    private function matchOrCreateCustomer(stdClass $input, string $channelId): array
    {
        $name=trim((string)($input->senderName??'Unknown Customer')); $company=trim((string)($input->company??''));$email=trim((string)($input->email??''));$phone=trim((string)($input->phone??''));$externalUserId=trim((string)($input->externalUserId??''));
        if($externalUserId!==''){$prior=$this->repo('ExternalConversation')->where(['channelId'=>$channelId,'externalUserId'=>$externalUserId])->findOne();if($prior){foreach(['account','contact','lead'] as $type){$id=$prior->get($type.'Id');if($id)return ['links'=>[$type.'Id'=>$id],'created'=>false];}}}
        foreach([['Contact','contact'],['Lead','lead']] as [$type,$link]){
            $person=null;if($email!=='')$person=$this->repo($type)->where(['emailAddress'=>$email])->findOne();if(!$person&&$phone!=='')$person=$this->repo($type)->where(['phoneNumber'=>$phone])->findOne();
            if($person)return ['links'=>[$link.'Id'=>$person->getId()],'created'=>false];
        }
        if($company!==''){$account=$this->repo('Account')->where(['name'=>$company,'billingAddressCountry'=>(string)($input->country??'')])->findOne();if($account)return ['links'=>['accountId'=>$account->getId()],'created'=>false];}
        $lead=null;if($company!=='')$lead=$this->repo('Lead')->where(['accountName'=>$company,'addressCountry'=>(string)($input->country??'')])->findOne();if(!$lead&&$name!=='')$lead=$this->repo('Lead')->where(['lastName'=>$name,'accountName'=>$company])->findOne();
        if($lead)return ['links'=>['leadId'=>$lead->getId()],'created'=>false];
        $lead=$this->create('Lead',['lastName'=>$name?:'Unknown Customer','accountName'=>$company,'addressCountry'=>(string)($input->country??''),'emailAddress'=>(string)($input->email??''),'status'=>'New','source'=>'Web Site','description'=>'由统一询盘自动创建，待人工确认。']);
        return ['links'=>['leadId'=>$lead->getId()],'created'=>true];
    }
    private function taskPayload(Entity $task): array { $draft=$this->requireEntity('AIReplyDraft',(string)$task->get('replyDraftId')); return ['id'=>$task->getId(),'idempotencyKey'=>$task->get('idempotencyKey'),'conversationId'=>$task->get('conversationId'),'channelId'=>$task->get('channelId'),'body'=>$draft->get('draftText'),'claimExpiresAt'=>$task->get('claimExpiresAt')]; }
    private function ownedTask(string $id,string $key): Entity { $task=$this->requireEntity('OutboundTask',$id); if($key===''||$task->get('claimedBy')!==$key) throw new Conflict('Task is not claimed by this agent.'); return $task; }
    private function syncConversation(Entity $task,string $status): void { $c=$this->requireEntity('ExternalConversation',(string)$task->get('conversationId'));$c->set('status',$status);$this->em->saveEntity($c); }
    private function requireEntity(string $type,string $id): Entity { $e=$this->em->getEntityById($type,$id); if(!$e) throw new NotFound("$type not found."); return $e; }
    private function repo(string $type) { return $this->em->getRDBRepository($type); }
    private function create(string $type,array $values): Entity { $e=$this->em->getNewEntity($type);$e->set($values);$this->em->saveEntity($e);return $e; }
    private function now(): string { return gmdate('Y-m-d H:i:s'); }
    private function audit(string $event,string $actorType,string $actorId,string $entityType,string $entityId,string $result='success',array $details=[]): void { $this->create('AutomationAudit',['name'=>$event.' '.date('H:i:s'),'eventType'=>$event,'actorType'=>$actorType,'actorId'=>$actorId,'entityType'=>$entityType,'entityId'=>$entityId,'result'=>$result,'details'=>$details]); }
}
