<?php
namespace Espo\Custom\Tools\Fusanhe\Api;

use Espo\Core\Api\Request;
use Espo\Core\Api\Response;
use Espo\Core\Acl;
use Espo\Entities\User;
use Espo\ORM\EntityManager;
use Espo\Custom\Tools\Fusanhe\OutreachEvidenceService;

final class PostOutreachEvidence extends AbstractFusanheAction
{
    public function __construct(User $user, Acl $acl, EntityManager $em, private OutreachEvidenceService $service)
    { parent::__construct($user, $acl, $em); }

    public function process(Request $request): Response
    {
        $this->requireScope('OutreachEvidence', 'create');
        $body = $request->getParsedBody();
        $targetType = is_string($body->targetType ?? null) ? $body->targetType : '';
        $targetId = is_string($body->targetId ?? null) ? $body->targetId : '';
        if ($targetType !== '' && $targetId !== '') $this->requireEntityScope($targetType, $targetId, 'read');
        foreach (['conversationId' => 'ExternalConversation', 'messageId' => 'ExternalMessage'] as $field => $entity) {
            $value = is_string($body->{$field} ?? null) ? trim($body->{$field}) : '';
            if ($value !== '') $this->requireEntityScope($entity, $value, 'read');
        }
        return $this->json($request, $this->service->record($body, $this->user), 201);
    }
}
