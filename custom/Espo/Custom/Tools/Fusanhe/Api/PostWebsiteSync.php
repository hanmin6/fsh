<?php
namespace Espo\Custom\Tools\Fusanhe\Api;
use Espo\Core\Api\{Action,Request,Response,ResponseComposer};
use Espo\Core\Exceptions\BadRequest;
use Espo\Custom\Tools\Fusanhe\{AutomationAuth,WebsiteSyncService,SalesPolicy};
final class PostWebsiteSync implements Action
{
    public function __construct(private AutomationAuth $auth,private WebsiteSyncService $service) {}
    public function process(Request $request): Response
    {
        $agent=$this->auth->assertAgent($request);$body=$request->getParsedBody();
        if(!$body instanceof \stdClass||strlen(json_encode($body))>262144)throw new BadRequest('Bounded JSON object required.');
        return ResponseComposer::json($this->service->sync(SalesPolicy::data($body),$agent));
    }
}
