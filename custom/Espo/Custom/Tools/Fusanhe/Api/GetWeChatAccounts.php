<?php
namespace Espo\Custom\Tools\Fusanhe\Api;
use Espo\Core\Api\Request;
use Espo\Core\Api\Response;
use Espo\Core\Exceptions\Forbidden;
use Espo\Custom\Tools\Fusanhe\WeChatApi;
use Espo\Custom\Tools\Fusanhe\WeChatAccounts;
use Espo\Custom\Tools\Fusanhe\WeChatAgentStore;
final class GetWeChatAccounts extends AbstractFusanheAction
{
    public function process(Request $request): Response
    {
        if (!$this->user->isAdmin()) throw new Forbidden('微信接入管理需要管理员权限。');
        $response = $this->json($request, (new WeChatAccounts(new WeChatApi()))->listing()+['agent'=>(new WeChatAgentStore())->settings()]);
        $response->setHeader('Cache-Control', 'no-store'); return $response;
    }
}
