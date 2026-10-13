<?php
namespace Espo\Custom\Tools\Fusanhe\Api;
use Espo\Core\Api\Request;
use Espo\Core\Api\Response;
use Espo\Core\Exceptions\BadRequest;
use Espo\Core\Exceptions\Forbidden;
use Espo\Custom\Tools\Fusanhe\{MorningReportStore, MorningReportService};
final class GetMorningReport extends AbstractFusanheAction
{
    public function process(Request $request): Response
    {
        $date = (string) ($request->getQueryParam('date') ?? '');
        $service = new MorningReportService($this->em, new MorningReportStore());
        if ($date !== '') {
            // Same company-wide report explicitly approved for all recipients; source record links retain CRM ACL.
            $this->requireScope('Lead', 'read'); $this->requireScope('ExternalConversation', 'read');
            if (!MorningReportStore::validDate($date)) throw new BadRequest('invalid_report_date');
            $payload = $service->view($date, $this->user->isAdmin());
        } else {
            if (!$this->user->isAdmin()) throw new Forbidden('晨报管理需要管理员权限。');
            $payload = $service->overview();
        }
        $response = $this->json($request, $payload); $response->setHeader('Cache-Control', 'no-store'); return $response;
    }
}
