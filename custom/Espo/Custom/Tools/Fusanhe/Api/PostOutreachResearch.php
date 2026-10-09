<?php
namespace Espo\Custom\Tools\Fusanhe\Api;

use Espo\Core\Api\Request;
use Espo\Core\Api\Response;
use Espo\Core\Acl;
use Espo\Entities\User;
use Espo\ORM\EntityManager;
use Espo\Custom\Tools\Fusanhe\OutreachEvidenceService;

final class PostOutreachResearch extends AbstractFusanheAction
{
    public function __construct(User $user, Acl $acl, EntityManager $em, private OutreachEvidenceService $service)
    { parent::__construct($user, $acl, $em); }

    public function process(Request $request): Response
    {
        $this->requireScope('OutreachEvidence', 'edit');
        $entity = $this->requireEntityScope('OutreachEvidence', (string) $request->getRouteParam('id'), 'edit');
        return $this->json($request, $this->service->research($entity, $this->user));
    }
}
