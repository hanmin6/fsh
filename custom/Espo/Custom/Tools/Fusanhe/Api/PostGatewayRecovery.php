<?php
namespace Espo\Custom\Tools\Fusanhe\Api;

use Espo\Core\Api\Action;
use Espo\Core\Api\Request;
use Espo\Core\Api\Response;
use Espo\Core\Api\ResponseComposer;
use Espo\Core\Exceptions\BadRequest;
use Espo\Custom\Tools\Fusanhe\AutomationAuth;
use Espo\Custom\Tools\Fusanhe\GatewayRecoveryService;

final class PostGatewayRecovery implements Action
{
    public function __construct(private AutomationAuth $auth, private GatewayRecoveryService $service) {}
    public function process(Request $request): Response
    {
        $agent = $this->auth->assertAgent($request);
        $input = $request->getParsedBody();
        if (!$input instanceof \stdClass) throw new BadRequest('JSON object body is required.');
        return ResponseComposer::json($this->service->execute($input, $agent));
    }
}
