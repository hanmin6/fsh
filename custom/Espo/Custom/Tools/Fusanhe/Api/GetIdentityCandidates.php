<?php
namespace Espo\Custom\Tools\Fusanhe\Api;

use Espo\Core\Api\Action;
use Espo\Core\Api\Request;
use Espo\Core\Api\Response;
use Espo\Core\Api\ResponseComposer;
use Espo\Core\Exceptions\BadRequest;
use Espo\Custom\Tools\Fusanhe\IdentityService;

/** Strong-evidence customer candidates; out-of-scope customers are filtered server side. */
final class GetIdentityCandidates implements Action
{
    public function __construct(private IdentityService $service) {}

    public function process(Request $request): Response
    {
        $id = $request->getRouteParam('id');
        $conversationId = $request->getQueryParam('conversationId');
        if (!$id || !$conversationId) {
            throw new BadRequest('id and conversationId are required.');
        }
        return ResponseComposer::json(['candidates' => $this->service->findCandidates($id, $conversationId)]);
    }
}
