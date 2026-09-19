<?php
namespace Espo\Custom\Tools\Fusanhe\Api;

use Espo\Core\Api\Request;
use Espo\Core\Api\Response;
use Espo\Core\Api\ResponseComposer;
use Espo\Core\Exceptions\BadRequest;
use Espo\Entities\User;
use Espo\ORM\EntityManager;
use Espo\Core\Acl;
use Espo\Custom\Tools\Fusanhe\QuoteService;

final class PostQuoteTransition extends AbstractFusanheAction
{
    public function __construct(
        User $user,
        Acl $acl,
        EntityManager $em,
        private QuoteService $service
    ) {
        parent::__construct($user, $acl, $em);
    }

    public function process(Request $request): Response
    {
        $this->requireFeature('quotes');
        $this->requireScope('FusanheQuote', 'edit');
        $id = $request->getRouteParam('id');
        $action = (string) $request->getRouteParam('action');
        if (!$id || $action === '') throw new BadRequest();
        $this->requireEntityScope('FusanheQuote', $id, 'edit');
        $body = $request->getParsedBody();
        switch ($action) {
            case 'submit':
                return ResponseComposer::json($this->service->submit($id, $this->user));
            case 'approve':
                return ResponseComposer::json($this->service->approve($id, $this->user));
            case 'accept':
                return ResponseComposer::json($this->service->accept($id, $this->user, $body));
            case 'reject':
                $reason = trim((string) ($body->reason ?? ''));
                if ($reason === '') throw new BadRequest('reason is required.');
                return ResponseComposer::json($this->service->reject($id, $this->user, $reason));
            case 'copy-revision':
                return ResponseComposer::json($this->service->copyRevision(
                    $id,
                    $this->user,
                    isset($body->note) ? (string) $body->note : null
                ));
            default:
                throw new BadRequest('Unknown quote action.');
        }
    }
}
