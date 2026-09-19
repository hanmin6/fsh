<?php
namespace Espo\Custom\Tools\Fusanhe\Api;

use Espo\Core\Api\Action;
use Espo\Core\Api\Request;
use Espo\Core\Api\Response;
use Espo\Core\Api\ResponseComposer;
use Espo\Core\Exceptions\BadRequest;
use Espo\Custom\Tools\Fusanhe\ControlService;

/** Human takeover / resume AI assist, validated and audited server side. */
final class PostConversationControl implements Action
{
    public function __construct(private ControlService $service) {}

    public function process(Request $request): Response
    {
        $id = $request->getRouteParam('id');
        $mode = (string) ($request->getParsedBody()->mode ?? '');
        if (!$id) {
            throw new BadRequest();
        }
        return ResponseComposer::json($this->service->setControlMode($id, $mode));
    }
}
