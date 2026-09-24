<?php
namespace Espo\Custom\Tools\Fusanhe\Api;
use Espo\Core\Api\Action;
use Espo\Core\Api\Request;
use Espo\Core\Api\Response;
use Espo\Core\Api\ResponseComposer;
use Espo\Custom\Tools\Fusanhe\BossInsightsService;
final class GetInsights implements Action
{
    public function __construct(private BossInsightsService $service) {}
    public function process(Request $request): Response
    {
        $id = $request->getRouteParam('id');
        return ResponseComposer::json($id ? $this->service->detail($id) : $this->service->overview(
            (string) ($request->getQueryParam('q') ?? ''), (string) ($request->getQueryParam('status') ?? ''),
            (int) ($request->getQueryParam('offset') ?? 0), (int) ($request->getQueryParam('limit') ?? 25)));
    }
}
