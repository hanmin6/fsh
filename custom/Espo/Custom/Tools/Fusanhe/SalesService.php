<?php
namespace Espo\Custom\Tools\Fusanhe;

use Espo\ORM\{Entity,EntityManager};
use Espo\Core\Exceptions\{BadRequest,Conflict};
use DateTimeImmutable;
use DateTimeZone;

/** Event-sensitive plans, minute execution and durable single-send boundaries. */
final class SalesService
{
    public function __construct(private EntityManager $em, private ServiceKernel $kernel, private SalesPlanner $planner, private SalesMailSender $sender) {}
    private function fresh(string $type,string $id): ?Entity {return $this->em->getRDBRepository($type)->where(['id'=>$id])->findOne();}
    private function value(Entity $e): array {return SalesPolicy::data($e->getValueMap());}
    public function candidates(int $limit=1000): array
    {
        $out=[];
        foreach (['Lead','Contact','Account'] as $type) {
            $where=$type==='Lead'?['OR'=>[['fusanheSourceSystem'=>['muse','xpoz','openoutreach']],['fusanheSalesEnrolled'=>true]]]:['fusanheSalesEnrolled'=>true];
            foreach ($this->em->getRDBRepository($type)->where($where)->order('createdAt','ASC')->limit(0,$limit)->find() as $e) $out[]=['type'=>$type,'id'=>$e->getId(),'name'=>$e->get('name'),'rating'=>AcquisitionRouting::effectiveRating($this->value($e)), 'profile'=>(array)($e->get('fusanheSalesProfile')??[])];
        }return $out;
    }
    public function context(string $type,string $id): array
    {
        if (!in_array($type,['Lead','Account','Contact'],true)||!preg_match('/^[A-Za-z0-9]{5,24}$/D',$id)) throw new BadRequest('Invalid customer.');
        $target=$this->fresh($type,$id);if (!$target) throw new BadRequest('Customer missing.');
        $customers=[$type.':'.$id=>$target];$conversations=[];$messages=[];
        if ($target->get('accountId')&&($account=$this->fresh('Account',$target->get('accountId')))) $customers['Account:'.$account->getId()]=$account;
        foreach ($this->em->getRDBRepository('ExternalConversation')->where([lcfirst($type).'Id'=>$id])->order('lastMessageAt','DESC')->limit(0,30)->find() as $c) {
            $conversations[]=$this->value($c);
            $channel=$this->fresh('ExternalChannel',(string)$c->get('channelId'));
            foreach (['Lead','Account','Contact'] as $t) if ($c->get(lcfirst($t).'Id')&&($related=$this->fresh($t,$c->get(lcfirst($t).'Id')))) $customers[$t.':'.$related->getId()]=$related;
            foreach ($this->em->getRDBRepository('ExternalMessage')->where(['conversationId'=>$c->getId()])->order('sentAt','DESC')->limit(0,8)->find() as $m) {
                $raw=(array)($m->get('rawPayload')??[]);
                $messages[]=['id'=>$m->getId(),'direction'=>$m->get('direction'),'sentAt'=>$m->get('sentAt'),'body'=>mb_substr((string)($raw['salesBody']??$m->get('body')),0,1600),'kind'=>$raw['salesKind']??'customer','from'=>$raw['senderAddress']??null,'createdAt'=>$m->get('createdAt'),'channelType'=>$channel?->get('type')];
            }
        }
        usort($messages,fn($a,$b)=>strcmp($a['sentAt']??'',$b['sentAt']??''));$messages=array_slice($messages,-16);
        $profile=(array)($target->get('fusanheSalesProfile')??[]);$settings=SalesStore::read();$products=SalesStore::approved();
        $latest=end($messages);$reception=ReceptionSettings::read();$mode=AcquisitionRouting::isAcquisition($this->value($target))?'acquisition':'platform';
        $latestInbound=$latest&&$latest['direction']==='inbound'&&$latest['kind']==='customer';
        $freshInbound=$latestInbound&&$latest['channelType']==='Email'&&$latest['sentAt']>=gmdate('Y-m-d H:i:s',time()-1800)&&$latest['createdAt']>=gmdate('Y-m-d H:i:s',time()-1800)
            &&(!$settings['enabled']||!$settings['activatedAt']||$latest['sentAt']>=$settings['activatedAt']||$latest['id']===$settings['reviewedSourceMessageId']);
        // Rest-time intake precedes value routing; manual takeover and refusal remain absolute.
        if ($freshInbound&&ReceptionSchedule::state($reception)['active']&&ReceptionSchedule::state($reception,new DateTimeImmutable($latest['sentAt'],new DateTimeZone('UTC')))['active']) {
            $mode='reception';
            if (filter_var($latest['from'],FILTER_VALIDATE_EMAIL)) $profile=array_replace($profile,['email'=>$latest['from'],'emailVerified'=>true,'emailSource'=>'客户实际来信 '.$latest['id']]);
            $profile=array_replace($profile,['timezone'=>'Asia/Shanghai','timezoneVerified'=>true,'timezoneSource'=>'公司休息时间接待规则']);
        }
        if (!empty($profile['productIds'])) $products=array_values(array_filter($products,fn($p)=>in_array($p['productId'],$profile['productIds'],true)));
        // Include related email peers: a duplicated CRM record never bypasses refusal or S/A.
        if (!empty($profile['email'])) foreach (['Lead','Contact','Account'] as $t) foreach ($this->em->getRDBRepository($t)->where(['emailAddress'=>$profile['email']])->limit(0,50)->find() as $peer) $customers[$t.':'.$peer->getId()]=$peer;
        $values=array_map(fn($e)=>$this->value($e),array_values($customers));$research=(array)($target->get('aiRatingData')??[]);
        $context=['target'=>['type'=>$type,'id'=>$id,'name'=>$target->get('name'),'company'=>$target->get('accountName')?:($research['company']['name']??''),'kind'=>$type==='Account'||str_starts_with((string)$target->get('fusanheSourceId'),'xpoz:')?'company':'person'],
            'mode'=>$mode,'receptionRevision'=>$reception['revision'],'receptionActive'=>ReceptionSchedule::state($reception)['active'],
            'sourceMessageId'=>$mode==='reception'?$latest['id']:null,
            'rating'=>AcquisitionRouting::effectiveRating($this->value($target)), 'block'=>SalesPolicy::block($values,$conversations,$mode==='reception'),
            'ratingReady'=>$target->get('ratingSource')!=='auto'||$target->get('aiRatingStatus')==='completed',
            'contactPolicy'=>$target->get('fusanheContactPolicy'), 'profile'=>$profile,
            'messages'=>$messages,'products'=>array_map(fn($c)=>array_intersect_key($c,array_flip(['productId','name','nameEn','applications','publicFacts','revision'])), $products),
            'signatureApproved'=>$settings['signatureApproved'],'signature'=>$settings['signature'],'settingsRevision'=>$settings['revision'],'activationEpoch'=>$settings['activationEpoch'],
            'maxUnansweredFollowups'=>$settings['maxUnansweredFollowups'], 'cooldownHours'=>$settings['cooldownHours'], 'nowUtc'=>gmdate('Y-m-d H:i:s'),
            'relatedPolicy'=>array_map(fn($v)=>['id'=>$v['id'],'rating'=>AcquisitionRouting::effectiveRating($v),'policy'=>$v['fusanheContactPolicy']??null,'doNotContact'=>$v['fusanheDoNotContact']??false],$values)];
        $context['candidateTimes']=[];
        if ($mode==='reception') {
            // Do not depend on the PHP process timezone when creating a local candidate.
            $time=(new DateTimeImmutable('@'.(int)(ceil((time()+120)/60)*60)))->setTimezone(new DateTimeZone('Asia/Shanghai'));
            if (ReceptionSchedule::state($reception,$time)['active'])$context['candidateTimes'][]=['local'=>$time->format('Y-m-d H:i:s'),'utc'=>$time->setTimezone(new DateTimeZone('UTC'))->format('Y-m-d H:i:s')];
        }
        elseif (in_array($profile['timezone']??'',DateTimeZone::listIdentifiers(),true)) {
            $start=(new DateTimeImmutable('now',new DateTimeZone($profile['timezone'])))->modify('+1 day')->setTime(9,0);
            for ($d=0;$d<10;$d++) { $day=$start->modify('+'.$d.' days');if ((int)$day->format('N')>5)continue;
                foreach ([9,11,15] as $h) {$time=$day->setTime($h,0);$context['candidateTimes'][]=['local'=>$time->format('Y-m-d H:i:s'),'utc'=>$time->setTimezone(new DateTimeZone('UTC'))->format('Y-m-d H:i:s')];}
            }
        }
        return $context;
    }
    public function profile(string $type,string $id,array $input,string $actor): array
    {
        $this->context($type,$id);$e=$this->fresh($type,$id);$old=(array)($e->get('fusanheSalesProfile')??[]);
        if (($input['revision']??0)!==($old['revision']??0)) throw new Conflict('客户资料已更新。');
        $p=[];foreach (['email','emailSource','timezone','timezoneSource','business','businessSource','language'] as $f) {$p[$f]=trim((string)($input[$f]??''));if (mb_strlen($p[$f])>2000) throw new BadRequest('资料过长。');}
        foreach (['emailVerified','timezoneVerified','paused'] as $f) {if (!is_bool($input[$f]??null)) throw new BadRequest('Invalid verification flag.');$p[$f]=$input[$f];}
        if ($p['email']&&!filter_var($p['email'],FILTER_VALIDATE_EMAIL)) throw new BadRequest('Invalid email.');
        if ($p['timezone']&&!in_array($p['timezone'],DateTimeZone::listIdentifiers(),true)) throw new BadRequest('Invalid timezone.');
        $policy=$input['contactPolicy']??'unknown';if (!in_array($policy,['unknown','allowed','optedOut','restricted'],true)) throw new BadRequest('Invalid contact policy.');
        $ids=$input['productIds']??[];if (!is_array($ids)||count($ids)>15) throw new BadRequest('Invalid products.');
        foreach ($ids as $pid) if (!is_string($pid)||!$this->fresh('FusanheProduct',$pid)) throw new BadRequest('Product missing.');
        $p+=['productIds'=>$ids,'revision'=>($old['revision']??0)+1,'verifiedBy'=>$actor,'verifiedAt'=>$this->kernel->now()];
        $e->set(['fusanheSalesProfile'=>$p,'fusanheSalesEnrolled'=>true,'fusanheContactPolicy'=>$policy,'fusanheDoNotContact'=>in_array($policy,['optedOut','restricted'],true)]);
        if ($p['emailVerified']&&$p['email']&&(!$e->get('emailAddress')||strtolower($e->get('emailAddress'))===strtolower($p['email'])))$e->set('emailAddress',$p['email']);
        $this->kernel->save($e);$this->kernel->audit('sales.profile','user',$actor,$type,$id,'success',['revision'=>$p['revision']]);return $p;
    }
    private function row(string $type,string $id): Entity
    {
        $key=$type.':'.$id;$row=$this->em->getRDBRepository('FusanheSalesPlan')->where(['targetKey'=>$key])->findOne();
        if ($row)return $row;
        $target=$this->fresh($type,$id);
        return $this->kernel->create('FusanheSalesPlan',['name'=>$target?->get('name')?:$key,'targetKey'=>$key,'targetType'=>$type,'targetId'=>$id,'status'=>'wait_data','generation'=>0,'unansweredCount'=>0,'assignedUserId'=>$target?->get('assignedUserId')]);
    }
    private function handoff(Entity $row,string $reason): void
    {
        if ($row->get('handoffTaskId'))return;
        $t=$this->kernel->create('Task',['name'=>'人工跟进 · '.$row->get('name'),'description'=>$reason,'status'=>'Not Started','parentType'=>$row->get('targetType'),'parentId'=>$row->get('targetId'),'assignedUserId'=>$row->get('assignedUserId')]);
        $row->set('handoffTaskId',$t->getId());
    }
    public function run(string $type,string $id,bool $force=false): array
    {
        return $this->locked($type.':'.$id,function()use($type,$id,$force){
            $context=$this->context($type,$id);$row=$this->row($type,$id);$hash=SalesPolicy::hash($context);
            if (in_array($row->get('status'),['sending','uncertain'],true)) return $this->value($row); // reconcile, never regenerate/resend.
            $dueReview=$row->get('nextEvaluationAt')&&$row->get('nextEvaluationAt')<=$this->kernel->now();
            if (!$force&&$row->get('contextHash')===$hash&&!$dueReview) return $this->value($row)+['unchanged'=>true];
            // New inbound breaks the no-response series. A manual outbound supersedes AI work.
            $latest=end($context['messages']);$latestId=$latest['id']??null;
            if (($latest['direction']??'')==='inbound'&&($latest['kind']??'')==='customer'&&SalesPolicy::refusal($latest['body']??'')) {
                $this->stop($type,$id);$context=$this->context($type,$id);$hash=SalesPolicy::hash($context);
            }
            if ($latestId&&$latestId!==$row->get('lastMessageId')&&($latest['direction']??'')==='inbound'&&($latest['kind']??'')==='customer') $row->set('unansweredCount',0);
            $row->set(['contextHash'=>$hash,'context'=>$context,'lastMessageId'=>$latestId,'errorCode'=>null,'nextEvaluationAt'=>null,'dueAt'=>null,'activationEpoch'=>SalesStore::read()['activationEpoch']]);
            if ($context['block']==='stopped') {$row->set(['status'=>'stopped','reason'=>'拒绝联系、无效地址或永久退信。']);}
            else if ($context['block']==='human'||($context['mode']!=='reception'&&in_array($context['rating'],['S','A'],true))) {
                $row->set(['status'=>'human','reason'=>'高价值客户或已由人工接管。']);$this->handoff($row,$row->get('reason'));
                if (!SalesPolicy::requirements($context)&&$force) {try {$row->set('plan',$this->planner->plan($context));}catch (\Throwable $e){$row->set('errorCode',$this->error($e));}}
            }
            else if ($context['mode']==='platform') {$row->set(['status'=>'wait_data','reason'=>'其他平台客户按休息时间接待，等待休息时段的新来信。']);}
            else if ($latestId&&($latest['direction']??'')==='outbound'&&$latestId!==$row->get('ownMessageId')) {$row->set(['status'=>'human','reason'=>'已有人工或其他渠道的回复，交人工续接。']);$this->handoff($row,$row->get('reason'));}
            else if (($missing=SalesPolicy::requirements($context))) {
                $row->set(['status'=>'wait_data','reason'=>'待补齐：'.implode('、',$missing)]);
                if ($force) {
                    $context['missingInformation']=$missing;$context['catalogNames']=array_map(fn($p)=>$p->get('name'),iterator_to_array($this->em->getRDBRepository('FusanheProduct')->find()));
                    $context['verifiedResearch']=SalesPolicy::data($this->fresh($type,$id)->get('fusanheSalesResearch'));
                    try {$row->set('plan',$this->planner->plan($context));}catch(\Throwable $e){$row->set('errorCode',$this->error($e));}
                }
            }
            else if ((int)$row->get('unansweredCount')>SalesStore::read()['maxUnansweredFollowups']) {$row->set(['status'=>'stopped','reason'=>'无人回复的主动跟进已达到上限。']);}
            else {
                $last=$row->get('lastSubmittedAt');
                if ($last&&(!$latest||$latest['direction']!=='inbound'||($latest['kind']??'')!=='customer')&&strtotime($last.' UTC')+SalesStore::read()['cooldownHours']*3600>time()) {$row->set(['status'=>'submitted','reason'=>'邮件已提交，等待客户回复。','nextEvaluationAt'=>gmdate('Y-m-d H:i:s',strtotime($last.' UTC')+SalesStore::read()['cooldownHours']*3600)]);}
                else {
                    $context['unansweredCount']=(int)$row->get('unansweredCount');$context['previousMail']=SalesPolicy::data($row->get('plan'));unset($context['previousMail']['bodyReview']);
                    $row->set(['status'=>'planning','reason'=>'正在匹配产品与规划联系时间。']);$this->kernel->save($row);
                    try {
                        $plan=$this->planner->plan($context);$fresh=$this->context($type,$id);
                        if (SalesPolicy::hash($fresh)!==$hash) throw new \RuntimeException('sales_context_changed');
                        $row->set(['plan'=>$plan,'generation'=>(int)$row->get('generation')+1,'reason'=>$plan['reason'],'nextEvaluationAt'=>$plan['nextEvaluationUtc']]);
                        $status=match($plan['action']) {'send'=>SalesStore::read()['enabled']?'scheduled':'preview','stop','skip'=>'stopped','human'=>'human',default=>'wait_data'};
                        $row->set(['status'=>$status,'dueAt'=>$plan['action']==='send'?$plan['dueUtc']:null,'recipient'=>strtolower($context['profile']['email']??'')]);
                        if ($status==='human')$this->handoff($row,$plan['reason']);
                        if ($plan['action']==='stop')$this->stop($type,$id);
                    } catch (\Throwable $e) {$row->set(['status'=>'failed','reason'=>'规划暂不可用，等待恢复。','errorCode'=>$this->error($e),'nextEvaluationAt'=>gmdate('Y-m-d H:i:s',time()+1800)]);}
                }
            }
            $this->kernel->save($row);return $this->value($row);
        });
    }
    private function error(\Throwable $e): string {return preg_match('/^(sales|text)_[a-z_0-9]+$/D',$e->getMessage())?$e->getMessage():'sales_processing_failed';}
    /** Preserve the exact first preview the operator reviewed when enabling the module. */
    public function activatePreview(string $id,int $generation): array
    {
        $row=$this->fresh('FusanheSalesPlan',$id);if(!$row)throw new Conflict('预览不存在。');
        return $this->locked($row->get('targetKey'),function()use($id,$generation){
            $row=$this->fresh('FusanheSalesPlan',$id);$settings=SalesStore::read();$plan=SalesPolicy::data($row->get('plan'));
            if(!$settings['enabled']||$row->get('status')!=='preview'||(int)$row->get('generation')!==$generation||($plan['model']??'')!==SalesPolicy::MODEL||($plan['action']??'')!=='send'||empty($plan['bodyReview']['approved'])||($plan['validUntilUtc']??'')<=gmdate('Y-m-d H:i:s',time()+60))throw new Conflict('预览已变化或过期，请重新核对。');
            $expected=SalesPolicy::data($row->get('context'));$expected['settingsRevision']=$settings['revision'];$expected['activationEpoch']=$settings['activationEpoch'];
            $context=$this->context($row->get('targetType'),$row->get('targetId'));
            if(SalesPolicy::requirements($context)||$context['block']||SalesPolicy::hash($expected)!==SalesPolicy::hash($context))throw new Conflict('客户或产品资料已变化，请重新预览。');
            $row->set(['status'=>'scheduled','activationEpoch'=>$settings['activationEpoch'],'context'=>$context,'contextHash'=>SalesPolicy::hash($context)]);$this->kernel->save($row);return $this->value($row);
        });
    }
    private function locked(string $key,\Closure $fn): array
    {
        $path=SalesStore::directory().'/'.hash('sha256',$key).'.lock';$lock=fopen($path,'c');
        if (!$lock)throw new \RuntimeException('sales_storage_unavailable');SalesStore::secure($path);
        if (!$lock||!flock($lock,LOCK_EX|LOCK_NB)) {if ($lock)fclose($lock);return ['status'=>'busy'];}
        try {return $fn();}finally {flock($lock,LOCK_UN);fclose($lock);}
    }
    public function stop(string $type,string $id): void
    {
        $e=$this->fresh($type,$id);if (!$e)return;
        $e->set(['fusanheDoNotContact'=>true,'fusanheContactPolicy'=>'optedOut']);$this->kernel->save($e);
        $email=((array)$e->get('fusanheSalesProfile'))['email']??$e->get('emailAddress');
        if ($email) foreach (['Lead','Contact','Account'] as $t) foreach ($this->em->getRDBRepository($t)->where(['emailAddress'=>$email])->find() as $peer) {$peer->set(['fusanheDoNotContact'=>true,'fusanheContactPolicy'=>'optedOut']);$this->kernel->save($peer);}
    }
    /** Fresh-read checks immediately before SMTP. */
    public function sendBlock(Entity $row,array $context,array $settings): ?string
    {
        if (!$settings['enabled']||!$row->get('activationEpoch')||$row->get('activationEpoch')!==$settings['activationEpoch'])return '模块未启用或任务属于旧授权。';
        if ($context['block']||($context['mode']!=='reception'&&!in_array($context['rating'],['B','C','D'],true))||$context['mode']==='platform')return '客户分流、拒联或人工接管已变化。';
        if ($context['mode']==='reception'&&(!$context['receptionActive']||!$context['sourceMessageId']))return '休息接待已结束或没有新来信。';
        if (SalesPolicy::requirements($context)||SalesPolicy::hash($context)!==$row->get('contextHash'))return '客户资料、消息或产品版本已变化。';
        $plan=SalesPolicy::data($row->get('plan'));
        if (($plan['model']??'')!==SalesPolicy::MODEL||($plan['action']??'')!=='send'||($plan['policyVersion']??'')!==SalesPolicy::VERSION||empty($plan['bodyReview']['approved']))return '计划审核或模型不符。';
        if (!$row->get('dueAt')||$row->get('dueAt')>$this->kernel->now()||($plan['validUntilUtc']??'')<$this->kernel->now())return '尚未到期或计划已过期。';
        $latest=end($context['messages']);
        if (($latest['direction']??'')!=='inbound'&&$row->get('lastSubmittedAt')&&strtotime($row->get('lastSubmittedAt').' UTC')+$settings['cooldownHours']*3600>time())return '客户联系间隔未到。';
        return null;
    }
    private function execute(Entity $candidate): array
    {
        return $this->locked($candidate->get('targetKey'),function()use($candidate){
            $row=$this->fresh('FusanheSalesPlan',$candidate->getId());if (!$row||$row->get('status')!=='scheduled')return ['status'=>'skipped'];
            $context=$this->context($row->get('targetType'),$row->get('targetId'));$settings=SalesStore::read();$reason=$this->sendBlock($row,$context,$settings);
            if ($reason) {$row->set(['status'=>'wait_data','reason'=>$reason,'contextHash'=>null]);$this->kernel->save($row);return ['status'=>'revoked'];}
            // Address-level durable cooldown and uncertain outcome block duplicated customer records.
            foreach ($this->em->getRDBRepository('FusanheSalesPlan')->where(['recipient'=>strtolower($context['profile']['email'])])->find() as $peer) {
                if ($peer->getId()===$row->getId())continue;
                if (in_array($peer->get('status'),['sending','uncertain'],true)||($peer->get('lastSubmittedAt')&&strtotime($peer->get('lastSubmittedAt').' UTC')+$settings['cooldownHours']*3600>time())) {$row->set(['status'=>'wait_data','reason'=>'相同邮箱有近期联系或待核实投递。','nextEvaluationAt'=>gmdate('Y-m-d H:i:s',time()+86400)]);$this->kernel->save($row);return ['status'=>'deduplicated'];}
            }
            $plan=SalesPolicy::data($row->get('plan'));
            try {$email=$this->sender->prepare($row,$context,$plan,$settings);}
            catch (\Throwable $e) {$row->set(['status'=>'failed','reason'=>'发件准备失败，尚未调用 SMTP。','errorCode'=>$this->error($e),'nextEvaluationAt'=>gmdate('Y-m-d H:i:s',time()+1800)]);$this->kernel->save($row);return ['status'=>'failed'];}
            // Preparation can involve IO. Refresh policy once more at the transport boundary.
            $context=$this->context($row->get('targetType'),$row->get('targetId'));$settings=SalesStore::read();
            if (($reason=$this->sendBlock($row,$context,$settings))) {$row->set(['status'=>'wait_data','reason'=>$reason,'contextHash'=>null]);$this->kernel->save($row);return ['status'=>'revoked'];}
            $row->set(['status'=>'sending','attemptStartedAt'=>$this->kernel->now(),'recipient'=>strtolower($context['profile']['email']),'nativeEmailId'=>$email->getId(),'rfcMessageId'=>$email->getMessageId()]);$this->kernel->save($row);
            // No retry after this durable boundary, including process death or DB commit failure.
            try {
                $this->sender->submit($email,$settings,$context);
                $row->set(['status'=>'submitted','lastSubmittedAt'=>$this->kernel->now(),'unansweredCount'=>(int)$row->get('unansweredCount')+1,'reason'=>'Zoho SMTP 已接收，等待客户回复；尚不代表送达。','nextEvaluationAt'=>max($plan['nextEvaluationUtc'],gmdate('Y-m-d H:i:s',time()+$settings['cooldownHours']*3600))]);
                $this->sender->record($row,$email,$context);$this->kernel->save($row);
                $this->kernel->audit('sales.submitted','system','sales','FusanheSalesPlan',$row->getId(),'success',['emailId'=>$email->getId(),'generation'=>$row->get('generation'),'model'=>SalesPolicy::MODEL]);
                return ['status'=>'submitted'];
            } catch (\Throwable $e) {$row->set(['status'=>'uncertain','reason'=>'SMTP 提交结果需核实，已禁止自动重发。','errorCode'=>'sales_delivery_uncertain']);$this->kernel->save($row);return ['status'=>'uncertain'];}
        });
    }
    public function tick(): array
    {
        return $this->locked('minute-tick',function(){
            $result=['evaluated'=>0,'submitted'=>0];$settings=SalesStore::read();
            // Any crashed transport is an uncertain send, never a retriable queued task.
            foreach ($this->em->getRDBRepository('FusanheSalesPlan')->where(['status'=>'sending','attemptStartedAt<'=>gmdate('Y-m-d H:i:s',time()-300)])->find() as $r) {$r->set(['status'=>'uncertain','reason'=>'执行中断，等待投递核实。']);$this->kernel->save($r);}
            if ($settings['enabled']) foreach ($this->em->getRDBRepository('FusanheSalesPlan')->where(['status'=>'scheduled','dueAt<='=>$this->kernel->now()])->order('dueAt','ASC')->find() as $r) {
                $last=$this->em->getRDBRepository('FusanheSalesPlan')->where(['attemptStartedAt>'=>gmdate('Y-m-d H:i:s',time()-$settings['transportIntervalSeconds'])])->findOne();if ($last) break;
                $sent=$this->execute($r);if (($sent['status']??'')==='submitted')$result['submitted']++;
            }
            // A finite processing batch bounds worker time; no daily customer quota.
            foreach ($this->candidates() as $c) {
                if ($result['evaluated']>=20)break;
                $r=$this->run($c['type'],$c['id']);if(empty($r['unchanged']))$result['evaluated']++;
                if (($r['plan']['plannedAt']??'')>=gmdate('Y-m-d H:i:s',time()-5))break;
            }
            return $result;
        });
    }
    /** Called by mailbox import after native/custom messages exist. No sends here. */
    public function receive(Entity $message,Entity $email,array $headers): void
    {
        $body=SalesPolicy::replyText((string)($email->getBodyPlainWithoutReplyPart()??$email->getBodyPlain()));
        $kind=SalesPolicy::classify((string)$email->getFromAddress(),(string)$email->getSubject(),$body,$headers);
        $raw=(array)($message->get('rawPayload')??[]);$raw['salesKind']=$kind;$raw['senderAddress']=$email->getFromAddress();$raw['rfcMessageId']=$email->getMessageId();$raw['references']=$headers['references']??'';
        $raw['salesBody']=$body;$message->set('rawPayload',$raw);$this->kernel->save($message);
        if ($kind==='customer'&&$message->get('direction')==='inbound') {
            $conv=$this->fresh('ExternalConversation',$message->get('conversationId'));
            foreach (['Lead','Account','Contact'] as $t) if ($conv?->get(lcfirst($t).'Id')&&($target=$this->fresh($t,$conv->get(lcfirst($t).'Id')))) {
                $target->set('fusanheSalesEnrolled',true);
                if ($target->get('ratingSource')!=='manual'&&!$target->get('fusanheDoNotContact')&&!SalesPolicy::refusal($body)) {
                    $target->set(['aiRatingStatus'=>'pending','aiRatingAttempts'=>0,'aiRatingNextAt'=>null,'aiRatingError'=>null]);
                }
                $this->kernel->save($target,['fusanheRating'=>true]);
            }
        }
        $ids=[];preg_match_all('/<[^>]+>/',($headers['references']??'').' '.($headers['inReplyTo']??'').' '.($email->getMessageId()??''),$ids);
        $matched=[];
        foreach(array_unique($ids[0]) as $rfc) {
            foreach($this->em->getRDBRepository('FusanheSalesPlan')->where(['rfcMessageId'=>$rfc])->find() as $r)$matched[$r->getId()]=$r;
            $original=$this->em->getRDBRepository('Email')->where(['messageId'=>$rfc])->findOne();
            if ($original&&str_starts_with($rfc,'<sales.')&&in_array($original->get('parentType'),['Lead','Contact','Account'],true)) {
                $r=$this->em->getRDBRepository('FusanheSalesPlan')->where(['targetKey'=>$original->get('parentType').':'.$original->get('parentId')])->findOne();if($r)$matched[$r->getId()]=$r;
            }
        }
        foreach ($matched as $r) {
            if ($message->get('direction')==='outbound') {
                // Sent-folder reconciliation proves a previously uncertain SMTP outcome.
                if ($email->getMessageId()===$r->get('rfcMessageId')&&in_array($r->get('status'),['sending','uncertain'],true)) {
                    $c=$this->fresh('ExternalConversation',$message->get('conversationId'));
                    if ($c) {$c->set(lcfirst($r->get('targetType')).'Id',$r->get('targetId'));if(!$c->get('controlOrigin'))$c->set('controlMode','aiAssist');$this->kernel->save($c);}
                    $r->set(['status'=>'submitted','nativeEmailId'=>$email->getId(),'ownMessageId'=>$message->getId(),'lastMessageId'=>$message->getId(),'lastSubmittedAt'=>$email->get('dateSent')?:$this->kernel->now(),'unansweredCount'=>(int)$r->get('unansweredCount')+1,'reason'=>'Zoho 已发邮件已核实。','nextEvaluationAt'=>gmdate('Y-m-d H:i:s',time()+SalesStore::read()['cooldownHours']*3600)]);
                    $raw=SalesPolicy::data($message->get('rawPayload'));$raw['salesPlanSnapshot']=SalesPolicy::data($r->get('plan'));$raw['salesPlanId']=$r->getId();$message->set(['rawPayload'=>$raw,'automationKind'=>'aiSales']);$this->kernel->save($message);$this->kernel->save($r);
                }continue;
            }
            $conversation=$this->fresh('ExternalConversation',$message->get('conversationId'));
            if ($conversation&&!$conversation->get(lcfirst($r->get('targetType')).'Id')) {$conversation->set(lcfirst($r->get('targetType')).'Id',$r->get('targetId'));$this->kernel->save($conversation);}
            if ($kind==='customer'&&!SalesPolicy::refusal($body)) {
                $target=$this->fresh($r->get('targetType'),$r->get('targetId'));
                if($target&&$target->get('ratingSource')!=='manual'&&!$target->get('fusanheDoNotContact')){$target->set(['aiRatingStatus'=>'pending','aiRatingAttempts'=>0,'aiRatingNextAt'=>null,'aiRatingError'=>null]);$this->kernel->save($target,['fusanheRating'=>true]);}
            }
            if ($kind==='bounce') {
                $e=$this->fresh($r->get('targetType'),$r->get('targetId'));$e->set(['fusanheDoNotContact'=>true,'fusanheContactPolicy'=>'restricted']);$this->kernel->save($e);$r->set(['status'=>'stopped','reason'=>'收到退信，地址暂停，需核实后恢复。']);
            }
            elseif ($kind==='customer'&&SalesPolicy::refusal($body)) {$this->stop($r->get('targetType'),$r->get('targetId'));$r->set(['status'=>'stopped','contextHash'=>null,'reason'=>'客户要求停止联系。']);}
            elseif ($kind==='customer') {$r->set(['status'=>'wait_data','contextHash'=>null,'unansweredCount'=>0,'reason'=>'收到客户回复，等待重新规划。']);}
            elseif ($kind==='autoReply') {$r->set(['status'=>'wait_data','contextHash'=>null,'reason'=>'收到自动回复，先评估返回时间。']);}
            $this->kernel->save($r);
        }
    }
}
