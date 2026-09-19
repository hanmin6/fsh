<?php
namespace Espo\Custom\Tools\Fusanhe\Api;

use Espo\Core\Api\Action;
use Espo\Core\Api\Request;
use Espo\Core\Api\Response;
use Espo\Core\Api\ResponseComposer;
use Espo\Core\Exceptions\BadRequest;
use Espo\Custom\Tools\Fusanhe\IdentityService;

/** Explicit customer creation from an unlinked identity - never silent. */
final class PostIdentityCreateCustomer implements Action
{
    public function __construct(private IdentityService $service) {}

    public function process(Request $request): Response
    {
        $id = $request->getRouteParam('id');
        $body = $request->getParsedBody();
        $conversationId = (string) ($body->conversationId ?? '');
        $targetType = (string) ($body->targetType ?? 'Lead');
        if (!$id || !$conversationId) {
            throw new BadRequest('id and conversationId are required.');
        }
        return ResponseComposer::json($this->service->createCustomer($id, $conversationId, $targetType));
    }
}
