<?php
namespace Espo\Custom\Tools\Fusanhe\Api;
use Espo\Core\Api\Request;
use Espo\Core\Api\Response;
use Espo\Core\Exceptions\{Forbidden,BadRequest};
use Espo\Custom\Tools\Fusanhe\{WeChatAgentStore,WeChatAccounts,WeChatApi,ServiceKernel};
final class PostWeChatAgent extends AbstractFusanheAction
{
    public function process(Request $request): Response
    {
        if(!$this->user->isAdmin())throw new Forbidden('微信客户助手管理需要管理员权限。');
        $input=(array)$request->getParsedBody();if(!is_bool($input['enabled']??null))throw new BadRequest('invalid_enabled');
        $s=(new WeChatAgentStore())->configure($input['enabled'],$this->user->getId());
        if($s['enabled']){ $accounts=new WeChatAccounts(new WeChatApi());foreach($accounts->listing()['accounts'] as $a)if($a['status']==='bound'&&$a['agentEnabled'])$accounts->update($a['id'],'agent',['enabled'=>true]); }
        (new ServiceKernel($this->em))->audit('wechat.agent.configure','user',$this->user->getId(),'ExternalChannel','wechat-agent','success',['enabled'=>$s['enabled'],'scope'=>'all']);
        $r=$this->json($request,['agent'=>$s]);$r->setHeader('Cache-Control','no-store');return $r;
    }
}
