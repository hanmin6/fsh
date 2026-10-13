<?php
namespace Espo\Custom\Tools\Fusanhe\Api;
use Espo\Core\Api\Request;
use Espo\Core\Api\Response;
use Espo\Custom\Tools\Fusanhe\ReceptionSettings;
use Espo\Custom\Tools\Fusanhe\ReceptionSchedule;
use Espo\Custom\Tools\Fusanhe\ServiceKernel;
final class GetReceptionSettings extends AbstractFusanheAction
{
    public function process(Request $request): Response
    {
        $this->requireScope('ExternalConversation', 'read');
        $ready = false;
        foreach ($this->em->getRDBRepository('AutomationAgent')->where(['status' => 'online'])->find() as $agent) {
            $heartbeat = $agent->get('lastHeartbeatAt');
            if (in_array('Alibaba', (array) $agent->get('capabilities'), true) && $heartbeat && strtotime($heartbeat . ' UTC') >= time() - 180) $ready = true;
        }
        return $this->json($request, ['settings' => ReceptionSettings::read(), 'state' => ReceptionSchedule::state(ReceptionSettings::read()), 'executionReady' => $ready, 'canEdit' => $this->user->isAdmin(), 'executionChannels' => ['Alibaba'], 'receptionMode' => '需求收集与人工交接']);
    }
}
