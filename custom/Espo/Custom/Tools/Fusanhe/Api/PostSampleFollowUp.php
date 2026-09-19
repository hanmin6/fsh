<?php
namespace Espo\Custom\Tools\Fusanhe\Api;

use Espo\Core\Api\Request;
use Espo\Core\Api\Response;
use Espo\Core\Api\ResponseComposer;
use Espo\Core\Exceptions\BadRequest;
use Espo\Entities\User;
use Espo\ORM\EntityManager;
use Espo\Core\Acl;
use Espo\Custom\Tools\Fusanhe\SampleService;

final class PostSampleFollowUp extends AbstractFusanheAction
{
    public function __construct(
        User $user,
        Acl $acl,
        EntityManager $em,
        private SampleService $service
    ) {
        parent::__construct($user, $acl, $em);
    }

    public function process(Request $request): Response
    {
        $this->requireFeature('samples');
        if (!$this->user->isAdmin() && (!$this->acl->checkScope('Task', 'create') || !$this->acl->checkScope('FusanheSample', 'read'))) {
            throw new \Espo\Core\Exceptions\Forbidden('Not allowed to create sample follow-ups.');
        }
        $id = $request->getRouteParam('id');
        if (!$id) throw new BadRequest();
        $this->requireEntityScope('FusanheSample', $id, 'read');
        $body = $request->getParsedBody();
        return ResponseComposer::json($this->service->createFollowUp(
            $id,
            $this->user,
            isset($body->intent) ? (string) $body->intent : null,
            isset($body->note) ? (string) $body->note : null
        ));
    }
}
