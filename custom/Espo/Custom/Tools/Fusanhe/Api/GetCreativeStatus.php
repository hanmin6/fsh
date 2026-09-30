<?php
namespace Espo\Custom\Tools\Fusanhe\Api;
use Espo\Core\Api\Request;
use Espo\Core\Api\Response;
use Espo\Core\Acl;
use Espo\Entities\User;
use Espo\ORM\EntityManager;
use Espo\Custom\Tools\Fusanhe\CreativeService;
final class GetCreativeStatus extends AbstractFusanheAction
{
    public function __construct(User $user, Acl $acl, EntityManager $em, private CreativeService $service)
    { parent::__construct($user, $acl, $em); }
    public function process(Request $request): Response
    {
        $this->requireScope('MediaJob', 'read');
        return $this->json($request, $this->service->status($this->user));
    }
}
