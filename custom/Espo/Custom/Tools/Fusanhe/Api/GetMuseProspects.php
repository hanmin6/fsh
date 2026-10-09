<?php

namespace Espo\Custom\Tools\Fusanhe\Api;

use Espo\Core\Api\Action;
use Espo\Core\Api\Request;
use Espo\Core\Api\Response;
use Espo\Core\Api\ResponseComposer;
use Espo\Custom\Tools\Fusanhe\AutomationAuth;
use Espo\Custom\Tools\Fusanhe\MuseCrmService;
use Espo\Custom\Tools\Fusanhe\Api\RequestContext;
use stdClass;

final class GetMuseProspects implements Action
{
    public function __construct(
        private MuseCrmService $service,
        private AutomationAuth $auth,
    ) {}

    public function process(Request $request): Response
    {
        $agent = $this->auth->assertAgent($request);
        $input = new stdClass();
        foreach (['sourceId', 'email', 'phone', 'name', 'limit'] as $field) {
            $value = $request->getQueryParam($field);
            if ($value !== null) {
                $input->{$field} = $value;
            }
        }
        return ResponseComposer::json(['requestId' => RequestContext::requestId()] + $this->service->searchProspects($input, $agent));
    }
}
