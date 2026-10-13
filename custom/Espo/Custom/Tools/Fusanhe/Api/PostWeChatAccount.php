<?php
namespace Espo\Custom\Tools\Fusanhe\Api;
use Espo\Core\Api\Request;
use Espo\Core\Api\Response;
use Espo\Core\Exceptions\BadRequest;
use Espo\Core\Exceptions\Forbidden;
use Espo\Custom\Tools\Fusanhe\WeChatApi;
use Espo\Custom\Tools\Fusanhe\WeChatAccounts;
use Espo\Custom\Tools\Fusanhe\ServiceKernel;
final class PostWeChatAccount extends AbstractFusanheAction
{
    public function process(Request $request): Response
    {
        if (!$this->user->isAdmin()) throw new Forbidden('微信接入管理需要管理员权限。');
        $input = json_decode(json_encode($request->getParsedBody()), true) ?? [];
        $id = (string) ($request->getRouteParam('id') ?? '');
        $action = $id === '' ? 'create' : (string) ($input['action'] ?? '');
        $service = new WeChatAccounts(new WeChatApi());
        try { $account = $action === 'create' && $id === '' ? $service->create((string) ($input['name'] ?? '')) : $service->update($id, $action, $input); }
        catch (\InvalidArgumentException $e) { throw new BadRequest($e->getMessage()); }
        catch (\RuntimeException $e) { throw new BadRequest(in_array($e->getMessage(), ['qr_unavailable', 'poll_unavailable'], true) ? $e->getMessage() : 'wechat_unavailable'); }
        if (!in_array($action, ['poll', 'verify'], true)) (new ServiceKernel($this->em))->audit('wechat.' . $action, 'user', $this->user->getId(), 'ExternalChannel', $account['id'], $account['error'] ? 'failure' : 'success', ['status' => $account['status'], 'error' => $account['error']]);
        $response = $this->json($request, ['account' => $account]);
        $response->setHeader('Cache-Control', 'no-store'); return $response;
    }
}
