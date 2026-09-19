<?php
namespace Espo\Custom\Tools\Fusanhe\Api;

use Espo\Core\Api\Action;
use Espo\Core\Api\Request;
use Espo\Core\Api\Response;
use Espo\Core\Api\ResponseComposer;
use Espo\Core\Exceptions\BadRequest;
use Espo\Custom\Tools\Fusanhe\IdentityService;

final class PostIdentityLink implements Action
{
    public function __construct(private IdentityService $service) {}

    public function process(Request $request): Response
    {
        $id = $request->getRouteParam('id');
        $body = $request->getParsedBody();
        $conversationId = (string) ($body->conversationId ?? '');
        $targetType = (string) ($body->targetType ?? '');
        $targetId = (string) ($body->targetId ?? '');
        if (!$id || !$conversationId || !$targetId) {
            throw new BadRequest('id, conversationId and targetId are required.');
        }
        return ResponseComposer::json($this->service->link($id, $conversationId, $targetType, $targetId));
    }
}
