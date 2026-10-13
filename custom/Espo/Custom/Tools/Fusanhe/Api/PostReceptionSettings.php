<?php
namespace Espo\Custom\Tools\Fusanhe\Api;
use Espo\Core\Api\Request;
use Espo\Core\Api\Response;
use Espo\Custom\Tools\Fusanhe\ReceptionSettings;
use Espo\Custom\Tools\Fusanhe\ReceptionSchedule;
use Espo\Custom\Tools\Fusanhe\ServiceKernel;
final class PostReceptionSettings extends AbstractFusanheAction
{
    public function process(Request $request): Response
    {
        if (!$this->user->isAdmin()) throw new \Espo\Core\Exceptions\Forbidden('Only administrators may change automatic reception.');
        $input = json_decode(json_encode($request->getParsedBody()), true);
        $settings = (new ReceptionSettings(new ServiceKernel($this->em)))->update($input, $this->user->getId());
        return $this->json($request, ['settings' => $settings, 'state' => ReceptionSchedule::state($settings), 'canEdit' => true, 'executionChannels' => ['Alibaba']]);
    }
}
