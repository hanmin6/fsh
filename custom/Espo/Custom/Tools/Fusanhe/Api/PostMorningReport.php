<?php
namespace Espo\Custom\Tools\Fusanhe\Api;
use Espo\Core\Api\Request;
use Espo\Core\Api\Response;
use Espo\Core\Exceptions\BadRequest;
use Espo\Core\Exceptions\Forbidden;
use Espo\Custom\Tools\Fusanhe\{MorningReportStore, MorningReportService, ServiceKernel};
final class PostMorningReport extends AbstractFusanheAction
{
    public function process(Request $request): Response
    {
        if (!$this->user->isAdmin()) throw new Forbidden('晨报管理需要管理员权限。');
        $input = (array) $request->getParsedBody(); $store = new MorningReportStore();
        $now = new \DateTimeImmutable('now', new \DateTimeZone('UTC'));
        if (($input['action'] ?? '') === 'configure') {
            if (!is_bool($input['enabled'] ?? null)) throw new BadRequest('invalid_enabled');
            $payload = ['settings' => $store->configure($input['enabled'], $now)];
            (new ServiceKernel($this->em))->audit('morning.configure', 'user', $this->user->getId(), 'ExternalChannel', 'morning-report', 'success', ['enabled' => $input['enabled'], 'sendTime' => '09:00']);
        } elseif (($input['action'] ?? '') === 'preview') {
            $date = $now->setTimezone(new \DateTimeZone('Asia/Shanghai'))->format('Y-m-d');
            $payload = ['report' => (new MorningReportService($this->em, $store))->generate($date, $now), 'preview' => true];
        } else throw new BadRequest('invalid_action');
        $response = $this->json($request, $payload); $response->setHeader('Cache-Control', 'no-store'); return $response;
    }
}
