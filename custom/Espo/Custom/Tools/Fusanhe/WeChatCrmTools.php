<?php
namespace Espo\Custom\Tools\Fusanhe;
use Espo\Core\Acl;
use Espo\Core\AclManager;
use Espo\Entities\User;
use Espo\ORM\EntityManager;

/** User explicitly approved company-wide lookup and entry for authenticated bound WeChat users. */
final class WeChatCrmTools
{
    public function __construct(private EntityManager $em,private AclManager $aclManager,private ServiceKernel $kernel) {}
    private function actor(string $id): User
    {
        $u=$this->em->getEntityById('User',$id);
        if(!$u instanceof User||!$u->get('isActive')||!$u->isAdmin())throw new \RuntimeException('agent_actor_unavailable');return $u;
    }
    private function acl(string $actor,string $type,string $action): Acl
    {
        $a=new Acl($this->aclManager,$this->actor($actor));if(!$a->checkScope($type,$action))throw new \RuntimeException('agent_forbidden');return $a;
    }
    private function fields(string $type,object $e,Acl $acl): array
    {
        $out=['id'=>$e->getId(),'type'=>$type];
        foreach(['name','accountName','emailAddress','phoneNumber','description','status','assignedUserName','rating','aiRating','aiRatingStatus','ratingSource','addressCountry','billingAddressCountry'] as $f)if($acl->checkField($type,$f,'read'))$out[$f]=$e->get($f);
        return $out;
    }
    public static function url(array $r): string {return 'https://crm.fsh.digital/?workspace=customers&entity='.rawurlencode($r['type']).'&record='.rawurlencode($r['id']).'#Home/workspace';}
    public function search(string $actor,array $p,int $offset=0): array
    {
        $types=($p['type']??'all')==='all'?['Lead','Account','Contact']:[$p['type']];$results=[];$more=false;
        foreach($types as $type){
            if(!in_array($type,['Lead','Account','Contact'],true))throw new \InvalidArgumentException('agent_invalid_type');$acl=$this->acl($actor,$type,'read');$where=[];
            if(($p['query']??'')!==''){$q=str_replace(['%','_'],['\\%','\\_'],$p['query']);$where['OR']=[['name*'=>'%'.$q.'%']];if($type==='Lead')$where['OR'][]=['accountName*'=>'%'.$q.'%'];}
            $clauses=[];
            if(($p['country']??'')!==''){
                $aliases=['德国'=>['德国','Germany'],'英国'=>['英国','United Kingdom'],'美国'=>['美国','United States'],'中国'=>['中国','China'],'日本'=>['日本','Japan'],'法国'=>['法国','France']];
                $countries=$aliases[$p['country']]??[$p['country']];$field=$type==='Account'?'billingAddressCountry*':'addressCountry*';$clauses[]=['OR'=>array_map(fn($country)=>[$field=>'%'.$country.'%'],$countries)];
            }
            if(($p['rating']??'')!=='')$clauses[]=['OR'=>[['rating'=>$p['rating']],['rating'=>['',null],'ratingSource!='=>'manual','aiRatingStatus'=>'completed','aiRating'=>$p['rating']]]];
            if($clauses)$where['AND']=$clauses;
            foreach($this->em->getRDBRepository($type)->where($where)->order('createdAt','DESC')->order('id','ASC')->limit(0,$offset+6)->find() as $e)$results[]=$this->fields($type,$e,$acl);
        }
        $more=count($results)>$offset+5;
        return ['rows'=>array_slice($results,$offset,5),'more'=>$more];
    }
    public function detail(string $actor,array $ref): string
    {
        $type=$ref['type']??'';$id=$ref['id']??'';if(!in_array($type,['Lead','Account','Contact'],true)||!is_string($id))throw new \InvalidArgumentException('agent_invalid_record');
        $acl=$this->acl($actor,$type,'read');$e=$this->em->getEntityById($type,$id);if(!$e||!$acl->checkEntity($e,'read'))return '这条客户记录不存在或当前不可访问，请重新查询。';
        $r=$this->fields($type,$e,$acl);$rating=AcquisitionRouting::effectiveRating($r);$text="客户：".($r['name']??'未命名')."\n类型：".['Lead'=>'潜在客户','Account'=>'客户公司','Contact'=>'联系人'][$type]."\n";
        foreach(['accountName'=>'公司','emailAddress'=>'邮箱','phoneNumber'=>'电话','assignedUserName'=>'负责人'] as $f=>$label)$text.=$label.'：'.(($r[$f]??'')?:'未记录')."\n";
        $text.='评级：'.($rating?:'待评级')."\n备注：".mb_substr((string)($r['description']??'未记录'),0,400)."\n";
        $this->acl($actor,'ExternalConversation','read');$link=lcfirst($type).'Id';$convs=$this->em->getRDBRepository('ExternalConversation')->where([$link=>$id])->order('lastMessageAt','DESC')->limit(0,2)->find();$found=false;
        foreach($convs as $c){$found=true;$text.="\n最近沟通：".($c->get('name')?:'客户会话')."\n";
            $ma=$this->acl($actor,'ExternalMessage','read');
            if($ma->checkField('ExternalMessage','body','read'))foreach($this->em->getRDBRepository('ExternalMessage')->where(['conversationId'=>$c->getId()])->order('sentAt','DESC')->limit(0,3)->find() as $m)$text.=($m->get('direction')==='inbound'?'客户':'回复').'：'.mb_substr((string)$m->get('body'),0,180)."\n";
        }
        if(!$found)$text.="\n暂无已关联的沟通记录。\n";return mb_substr($text,0,3200)."\n打开CRM → ".self::url($r);
    }
    public function duplicates(string $actor,array $customer): array
    {
        $out=[];
        foreach(['Lead','Account','Contact'] as $type){$acl=$this->acl($actor,$type,'read');$where=['OR'=>[['name'=>$customer['name']]]];
            if($customer['email']!=='')$where['OR'][]=['emailAddress'=>$customer['email']];if($customer['phone']!=='')$where['OR'][]=['phoneNumber'=>$customer['phone']];
            foreach($this->em->getRDBRepository($type)->where($where)->limit(0,3)->find() as $e)$out[]=$this->fields($type,$e,$acl);
        }
        return $out;
    }
    public function create(string $actor,string $wechatId,string $operation,array $customers): array
    {
        $acl=$this->acl($actor,'Lead','create');$customers=WeChatAgentPlanner::customers($customers);
        foreach(['lastName','accountName','emailAddress','phoneNumber','addressCountry','description'] as $f)if(!$acl->checkField('Lead',$f,'edit'))throw new \RuntimeException('agent_forbidden');
        foreach($customers as $c)if($this->duplicates($actor,$c))throw new \RuntimeException('agent_duplicate');
        $tx=$this->em->getTransactionManager();$tx->start();$out=[];
        try{foreach($customers as $i=>$c){
            $key=hash('sha256',$wechatId.'|'.$operation.'|'.$i);$e=$this->em->getRDBRepository('Lead')->where(['fusanheWechatCreateKey'=>$key])->findOne();
            if(!$e){$e=$this->kernel->create('Lead',['lastName'=>$c['name'],'accountName'=>$c['company']?:null,'emailAddress'=>$c['email']?:null,'phoneNumber'=>$c['phone']?:null,'addressCountry'=>$c['country']?:null,'description'=>$c['note']?:null,'assignedUserId'=>$actor,'createdById'=>$actor,'fusanheWechatCreateKey'=>$key]);
                $this->kernel->audit('wechat.customer.create','wechat',$wechatId,'Lead',$e->getId(),'success',['crmActorId'=>$actor,'operationId'=>$operation]);}
            $out[]=['id'=>$e->getId(),'type'=>'Lead','name'=>$c['name']];
        }$tx->commit();return $out;}catch(\Throwable $e){$tx->rollback();throw $e;}
    }
}
