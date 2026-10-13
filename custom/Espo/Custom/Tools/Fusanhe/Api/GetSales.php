<?php
namespace Espo\Custom\Tools\Fusanhe\Api;
use Espo\Core\Api\{Request,Response};
use Espo\Custom\Tools\Fusanhe\{SalesStore,SalesPolicy};
final class GetSales extends SalesApi
{
    public function process(Request $request): Response
    {
        $this->requireScope('ExternalConversation','read');$plans=[];$customers=[];
        foreach ($this->em->getRDBRepository('FusanheSalesPlan')->order('modifiedAt','DESC')->limit(0,200)->find() as $row) {
            $target=$this->em->getEntityById($row->get('targetType'),$row->get('targetId'));
            if ($target&&($this->user->isAdmin()||$this->acl->checkEntityRead($target))) $plans[]=(array)$row->getValueMap();
        }
        foreach ($this->sales->candidates() as $c) {$target=$this->em->getEntityById($c['type'],$c['id']);if ($this->user->isAdmin()||$this->acl->checkEntityRead($target)) {
            $c['contactPolicy']=$target->get('fusanheContactPolicy');$data=SalesPolicy::data($target->get('aiRatingData'));$c['research']=['reason'=>$data['reason']??'','sources'=>$data['sources']??[],'missingInformation'=>$data['missingInformation']??[]];$c['salesResearch']=SalesPolicy::data($target->get('fusanheSalesResearch'));$customers[]=$c;
        }}
        $products=[];$cards=SalesStore::cards();foreach ($this->em->getRDBRepository('FusanheProduct')->find() as $p) $products[]=$cards[$p->getId()]??['productId'=>$p->getId(),'name'=>$p->get('name'),'nameEn'=>$p->get('nameEn')?:'','applications'=>'','publicFacts'=>'','source'=>'','validUntil'=>'','revision'=>0,'status'=>'draft'];
        $mailbox=$this->em->getEntityById('EmailAccount',SalesStore::read()['emailAccountId']);
        return $this->json($request,['settings'=>SalesStore::read(),'products'=>$products,'plans'=>$plans,'customers'=>$customers,'canEdit'=>$this->user->isAdmin(),'model'=>SalesPolicy::MODEL,'smtpReady'=>$mailbox?->get('status')==='Active'&&$mailbox?->get('useSmtp'),'phase'=>'Zoho 邮件；平台接待沿用休息时间规则']);
    }
}
