<?php
namespace Espo\Custom\Tools\Fusanhe\Api;

use Espo\Core\Api\Action;
use Espo\Core\Api\Request;
use Espo\Core\Api\Response;
use Espo\Core\Api\ResponseComposer;
use Espo\Core\Acl;
use Espo\Core\Exceptions\BadRequest;
use Espo\Core\Exceptions\Forbidden;
use Espo\Entities\User;
use Espo\ORM\EntityManager;
use Espo\Custom\Tools\Fusanhe\WorkflowService;

final class PostGenerateDraft extends AbstractFusanheAction
{
    public function __construct(
        private WorkflowService $service,
        User $user,
        Acl $acl,
        EntityManager $em
    ) {
        parent::__construct($user, $acl, $em);
    }

    public function process(Request $request): Response
    {
        if (!$this->user->isAdmin() && !$this->acl->checkScope('AIReplyDraft', 'create')) {
            throw new Forbidden('Not allowed to create drafts.');
        }
        $id = $request->getRouteParam('id');
        if (!$id) {
            throw new BadRequest();
        }
        $this->requireEntityScope('ExternalConversation', $id, 'read');
        $input = $request->getParsedBody();
        $choice = $input->modelChoice ?? null;
        if ($choice !== null && (!is_string($choice) || !in_array($choice, ['gpt', 'grok', 'gemini', 'legacy'], true))) throw new BadRequest('Invalid model choice.');
        try {
            return ResponseComposer::json($this->service->generateDraft($id, $this->user, $choice));
        } catch (\RuntimeException $error) {
            $safe = ['text_not_configured', 'text_invalid_choice', 'text_auth_failed', 'text_rate_limited', 'text_transport_failed', 'text_invalid_response','text_model_mismatch', 'text_incomplete_response', 'text_invalid_json', 'text_invalid_reply', 'text_invalid_evidence', 'text_response_too_large'];
            $code = in_array($error->getMessage(), $safe, true) ? $error->getMessage() : 'text_generation_failed';
            return $this->json($request, ['errorCode' => $code], 503);
        }
    }
}
