<?php
namespace Espo\Custom\Tools\Fusanhe\Api;
use Espo\Core\Api\{Request,Response};
use Espo\Core\Exceptions\{BadRequest,Conflict};
use Espo\Custom\Tools\Fusanhe\{SalesStore,SalesPolicy,ServiceKernel};
final class PostSales extends SalesApi
{
    public function process(Request $request): Response
    {
        $input=json_decode(json_encode($request->getParsedBody()),true);$action=$input['action']??'';$kernel=new ServiceKernel($this->em);
        if ($action==='settings') {
            $this->admin();$form=$input['settings']??[];
            if (!empty($form['enabled'])&&!SalesStore::read()['enabled']) {
                $row=$this->requireEntity('FusanheSalesPlan',(string)($form['reviewedPlanId']??''));$plan=SalesPolicy::data($row->get('plan'));
                $context=$this->sales->context($row->get('targetType'),$row->get('targetId'));
                if ($row->get('status')!=='preview'||SalesPolicy::requirements($context)||SalesPolicy::hash($context)!==$row->get('contextHash')||empty($plan['bodyReview']['approved'])||($plan['model']??'')!==SalesPolicy::MODEL)throw new Conflict('请先生成并核对当前可发送的首批预览。');
                if (($form['reviewedGeneration']??null)!==(int)$row->get('generation'))throw new Conflict('邮件预览已更新，请核对最新版本。');
                $old=SalesStore::read();foreach(['signature','signatureApproved','cooldownHours','maxUnansweredFollowups'] as $key)if(($form[$key]??null)!==$old[$key])throw new Conflict('请先保存署名或跟进规则，再生成和核对首封预览。');
                $form['reviewedSourceMessageId']=$context['sourceMessageId'];
            }
            $activate=!empty($form['enabled'])&&!SalesStore::read()['enabled'];$result=SalesStore::updateSettings($form);
            if ($activate) {
                try {$approved=$this->sales->activatePreview($form['reviewedPlanId'],$form['reviewedGeneration']);if(($approved['status']??'')!=='scheduled')throw new Conflict('预览正在更新，请稍后重试。');}
                catch(\Throwable $e){SalesStore::updateSettings(array_replace($result,['enabled'=>false]));throw new Conflict('预览已变化，自动邮件仍暂停；请重新核对。');}
            }
            $kernel->audit('sales.settings','user',$this->user->getId(),'FusanheSalesPlan','settings','success',['revision'=>$result['revision'],'enabled'=>$result['enabled']]);
        } elseif ($action==='product') {
            $this->admin();$id=(string)($input['productId']??'');$this->requireEntity('FusanheProduct',$id);
            $result=SalesStore::card($id,$input['card']??[],$this->user->getId());$kernel->audit('sales.product','user',$this->user->getId(),'FusanheProduct',$id,'success',['revision'=>$result['revision'],'status'=>$result['status']]);
        } elseif ($action==='enrich') {
            $this->admin();$type=(string)($input['type']??'');$id=(string)($input['id']??'');if(!in_array($type,['Lead','Contact','Account'],true))throw new BadRequest('Invalid target.');
            $this->requireEntityScope($type,$id,'edit');$target=$this->requireEntity($type,$id);$target->set('fusanheSalesResearch',null);$kernel->save($target);$result=['status'=>'pending'];
            // Queue only: the web lookup is performed by the worker, never holds an HTTP request.
        } elseif (in_array($action,['profile','preview','pause'],true)) {
            $type=(string)($input['type']??'');$id=(string)($input['id']??'');if (!in_array($type,['Lead','Contact','Account'],true))throw new BadRequest('Invalid target.');
            $target=$this->requireEntityScope($type,$id,'edit');
            if ($action==='profile')$result=$this->sales->profile($type,$id,$input['profile']??[],$this->user->getId());
            elseif ($action==='pause') {$profile=(array)($target->get('fusanheSalesProfile')??[]);$profile['paused']=true;$profile['revision']=($profile['revision']??0)+1;$target->set('fusanheSalesProfile',$profile);$kernel->save($target);$result=$this->sales->run($type,$id);$kernel->audit('sales.pause','user',$this->user->getId(),$type,$id);}
            else {$result=$this->sales->run($type,$id,true);$kernel->audit('sales.preview','user',$this->user->getId(),$type,$id,'success',['status'=>$result['status']??'busy']);}
        } else throw new BadRequest('Invalid sales action.');
        return $this->json($request,['result'=>$result]);
    }
}
