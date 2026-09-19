<?php
namespace Espo\Custom\Tools\Fusanhe\Api;

use Espo\Core\Api\Request;
use Espo\Core\Api\Response;
use Espo\Core\Api\ResponseComposer;
use Espo\Custom\Tools\Fusanhe\Features;

final class GetFeatures extends AbstractFusanheAction
{
    public function process(Request $request): Response
    {
        return ResponseComposer::json(['features' => Features::all()]);
    }
}
