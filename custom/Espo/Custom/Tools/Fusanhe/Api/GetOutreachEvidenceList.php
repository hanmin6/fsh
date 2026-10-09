<?php
namespace Espo\Custom\Tools\Fusanhe\Api;

use Espo\Core\Api\Request;
use Espo\Core\Api\Response;
use Espo\Core\Acl;
use Espo\Entities\User;
use Espo\ORM\EntityManager;
use Espo\Custom\Tools\Fusanhe\OutreachEvidencePolicy;
use Espo\Custom\Tools\Fusanhe\OutreachEvidenceService;

final class GetOutreachEvidenceList extends AbstractFusanheAction
{
    public function __construct(User $user, Acl $acl, EntityManager $em, private OutreachEvidenceService $service)
    { parent::__construct($user, $acl, $em); }

    public function process(Request $request): Response
    {
        $this->requireScope('OutreachEvidence', 'read');
        $targetType = (string) ($request->getQueryParam('targetType') ?? '');
        $targetId = (string) ($request->getQueryParam('targetId') ?? '');
        $targetType = OutreachEvidencePolicy::targetType($targetType);
        $targetId = OutreachEvidencePolicy::targetId($targetId);
        $this->requireEntityScope($targetType, $targetId, 'read');
        $offset = max(0, (int) ($request->getQueryParam('offset') ?? 0));
        $limit = min(50, max(1, (int) ($request->getQueryParam('limit') ?? 30)));
        return $this->json($request, $this->service->list($targetType, $targetId, $this->user, $offset, $limit));
    }
}
