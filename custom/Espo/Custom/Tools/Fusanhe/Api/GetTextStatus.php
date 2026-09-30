<?php
namespace Espo\Custom\Tools\Fusanhe\Api;

use Espo\Core\Api\Request;
use Espo\Core\Api\Response;
use Espo\Custom\Tools\Fusanhe\TextGateway;

final class GetTextStatus extends AbstractFusanheAction
{
    public function process(Request $request): Response
    {
        $this->requireScope('ExternalConversation', 'read');
        return $this->json($request, (new TextGateway())->status());
    }
}
