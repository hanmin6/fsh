<?php
namespace Espo\Custom\Tools\Fusanhe\Api;

use Espo\Core\Api\{Request,Response};
use Espo\Core\Acl;
use Espo\Core\Exceptions\{BadRequest,Forbidden};
use Espo\Entities\User;
use Espo\ORM\EntityManager;
use Espo\Custom\Tools\Fusanhe\MessageTranslationService;

final class PostTranslateMessages extends AbstractFusanheAction
{
    public function __construct(private MessageTranslationService $service, User $user, Acl $acl, EntityManager $em)
    { parent::__construct($user, $acl, $em); }

    public function process(Request $request): Response
    {
        $id = $request->getRouteParam('id');
        if (!$id) throw new BadRequest();
        $this->requireEntityScope('ExternalConversation', $id, 'read');
        $input = $request->getParsedBody(); $ids = $input->messageIds ?? null; $retry = $input->retry ?? false;
        if (!is_array($ids) || !array_is_list($ids) || !$ids || count($ids) > 6 || !is_bool($retry)) throw new BadRequest('Invalid translation request.');
        foreach ($ids as $messageId) if (!is_string($messageId) || !preg_match('/^[A-Za-z0-9_-]{1,100}$/D', $messageId)) throw new BadRequest('Invalid message ID.');
        if (count(array_unique($ids)) !== count($ids)) throw new BadRequest('Duplicate message IDs.');
        foreach (['body','translatedBody'] as $field) if (!$this->acl->checkField('ExternalMessage', $field, 'read')) throw new Forbidden('Message field is not readable.');
        // Authorize the full batch before translation, including cached records.
        foreach ($ids as $messageId) {
            $message = $this->requireEntityScope('ExternalMessage', $messageId, 'read');
            if ($message->get('conversationId') !== $id) throw new BadRequest('Message is outside this conversation.');
        }
        try { return $this->json($request, $this->service->translate($id, $ids, $retry)); }
        catch (\Throwable $error) { return $this->json($request, ['errorCode' => 'translation_failed'], 503); }
    }
}
