<?php
namespace Espo\Custom\Tools\Fusanhe;
use Espo\ORM\Entity;
use Espo\ORM\EntityManager;

/** Durable native CRM queue. Per-customer locks prevent duplicate paid jobs. */
final class CustomerRatingService
{
    public function __construct(private EntityManager $em, private TextGateway $gateway) {}
    public function pending(int $limit = 3): array
    {
        $out=[];
        foreach (['Lead','Account','Contact'] as $type) {
            $rows=$this->em->getRDBRepository($type)->where([
                'OR'=>[['aiRatingStatus'=>null],['aiRatingStatus'=>'pending'],['aiRatingStatus'=>'failed','aiRatingAttempts<'=>3,'aiRatingNextAt<='=>gmdate('Y-m-d H:i:s')],['aiRatingStatus'=>'running','aiRatingNextAt<='=>gmdate('Y-m-d H:i:s')]],
                'createdAt<'=>gmdate('Y-m-d H:i:s',time()-30),
            ])->order('createdAt','ASC')->limit(0,$limit)->find();
            foreach ($rows as $row) $out[]=['type'=>$type,'id'=>$row->getId()];
        }
        return array_slice($out,0,$limit);
    }
    private function save(Entity $e): void { $this->em->saveEntity($e,['fusanheRating'=>true,'fusanheService'=>true]); }
    public function snapshot(Entity $e): array
    {
        $customer=[];
        foreach (['name','firstName','lastName','accountName','website','emailAddress','addressCountry','billingAddressCountry','description'] as $f) {
            $value=(string)($e->get($f) ?? '');
            if ($f==='description') $value=preg_split('/\[sql-history:|\[history-import:/',$value)[0];
            $customer[$f]=mb_substr($value,0,$f==='description'?12000:500);
        }
        $messages=[];$total=0;$field=lcfirst($e->getEntityType()).'Id';
        $conversations=$this->em->getRDBRepository('ExternalConversation')->where([$field=>$e->getId()])->find();
        foreach ($conversations as $c) {
            $all=$this->em->getRDBRepository('ExternalMessage')->where(['conversationId'=>$c->getId()])->order('sentAt','DESC')->limit(0,150)->find();
            foreach ($all as $m) $messages[]=['id'=>$m->getId(),'conversationId'=>$c->getId(),'direction'=>$m->get('direction'),'sentAt'=>$m->get('sentAt'),'timestampConfidence'=>$m->get('timestampConfidence'),'body'=>mb_substr((string)$m->get('body'),0,5000)];
            $total+=$this->em->getRDBRepository('ExternalMessage')->where(['conversationId'=>$c->getId()])->count();
        }
        usort($messages,fn($a,$b)=>strcmp($b['sentAt']??'',$a['sentAt']??''));
        $messages=array_slice($messages,0,150);
        // Bound recent context and explicitly report any omitted history.
        $input=['customer'=>$customer,'messages'=>$messages,'totalMessages'=>$total];
        while (strlen(json_encode($input,JSON_UNESCAPED_UNICODE))>44000 && count($input['messages'])>1) array_pop($input['messages']);
        $input['includedMessages']=count($input['messages']);
        $input['historyTruncated']=$total>count($input['messages']);
        return $input;
    }
    public function run(string $type,string $id): array
    {
        if (!in_array($type,['Lead','Account','Contact'],true) || !preg_match('/^[a-zA-Z0-9]+$/D',$id)) throw new \InvalidArgumentException('rating_invalid_target');
        $lock=fopen('data/customer-rating-'.hash('sha256',$type.$id).'.lock','c');
        if (!$lock || !flock($lock,LOCK_EX|LOCK_NB)) {if ($lock) fclose($lock);return ['status'=>'busy'];}
        try {
            $e=$this->em->getEntityById($type,$id);
            if (!$e) return ['status'=>'missing'];
            if ($e->get('aiRatingStatus')==='completed') return ['status'=>'already_completed'];
            if ($e->get('aiRatingStatus')==='failed' && (int)$e->get('aiRatingAttempts')>=3) return ['status'=>'failed'];
            $input=$this->snapshot($e);
            $version=hash('sha256',json_encode([$input,CustomerRatingPolicy::VERSION,$this->gateway->fingerprint()]));
            $attempts=(int)$e->get('aiRatingAttempts')+1;
            $e->set(['aiRatingStatus'=>'running','aiRatingAttempts'=>$attempts,'aiRatingNextAt'=>gmdate('Y-m-d H:i:s',time()+600),'aiRatingError'=>null]);$this->save($e);
            try {
                $result=$this->gateway->research($input+['asOfUtc'=>gmdate('c')]);
                // Re-read after the network call to respect manual decisions made while researching.
                $fresh=$this->em->getRDBRepository($type)->where(['id'=>$id])->findOne();
                if (!$fresh) return ['status'=>'missing'];
                $data=$result['data'];$data['queries']=$result['queries'];$data['usageTokens']=$result['usageTokens'];
                $data['evidence']=array_values(array_map(fn($m)=>['id'=>$m['id'],'conversationId'=>$m['conversationId'],'quote'=>mb_substr($m['body'],0,220)],array_filter($input['messages'],fn($m)=>in_array($m['id'],$data['evidenceMessageIds'],true))));
                $data['historyTruncated']=$input['historyTruncated'];$data['includedMessages']=$input['includedMessages'];$data['totalMessages']=$input['totalMessages'];
                $fresh->set(['aiRating'=>$data['rating'],'aiRatingReason'=>$data['reason'],'aiRatingStatus'=>'completed','aiRatingAt'=>gmdate('Y-m-d H:i:s'),'aiRatingModel'=>$result['model'],'aiRatingData'=>$data,'aiRatingVersion'=>$version,'aiRatingNextAt'=>null,'aiRatingError'=>null,'aiCompanyName'=>$data['company']['name']]);
                if ($fresh->get('ratingSource')!=='manual' && !($fresh->get('rating') && !$fresh->get('ratingSource'))) $fresh->set(['rating'=>$data['rating'],'ratingReason'=>$data['reason'],'ratingSource'=>'auto','ratingConfirmedAt'=>null,'ratingConfirmedById'=>null]);
                $this->save($fresh);
                return ['status'=>'completed','rating'=>$data['rating'],'companyMatch'=>$data['company']['matchStatus'],'sources'=>count($data['sources'])];
            } catch (\Throwable $err) {
                $e=$this->em->getRDBRepository($type)->where(['id'=>$id])->findOne();
                if ($e) { $code=$err instanceof \RuntimeException && preg_match('/^rating_[a-z_0-9]+$/D',$err->getMessage())?$err->getMessage():'rating_processing_failed';
                    $e->set(['aiRatingStatus'=>'failed','aiRatingError'=>$code,'aiRatingNextAt'=>gmdate('Y-m-d H:i:s',time()+min(3600,300*$attempts))]);$this->save($e); }
                return ['status'=>'failed','error'=>$code ?? 'rating_processing_failed'];
            }
        } finally {flock($lock,LOCK_UN);fclose($lock);}
    }
    public function tick(): void {foreach ($this->pending(1) as $target) $this->run($target['type'],$target['id']);}
}
