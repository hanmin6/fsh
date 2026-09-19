<?php
namespace Espo\Custom\Tools\Fusanhe\Api;

use Espo\Core\Api\Action;
use Espo\Core\Api\Request;
use Espo\Core\Api\Response;
use Espo\Core\Api\ResponseComposer;
use Espo\Core\Exceptions\BadRequest;
use Espo\Custom\Tools\Fusanhe\ControlService;

final class PostTaskCancel implements Action
{
    public function __construct(private ControlService $service) {}

    public function process(Request $request): Response
    {
        $id = $request->getRouteParam('id');
        if (!$id) {
            throw new BadRequest();
        }
        return ResponseComposer::json($this->service->cancelTask($id));
    }
}
