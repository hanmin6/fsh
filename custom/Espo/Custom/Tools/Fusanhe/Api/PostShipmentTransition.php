<?php
namespace Espo\Custom\Tools\Fusanhe\Api;

use Espo\Core\Api\Request;
use Espo\Core\Api\Response;
use Espo\Core\Api\ResponseComposer;
use Espo\Core\Exceptions\BadRequest;
use Espo\Entities\User;
use Espo\ORM\EntityManager;
use Espo\Core\Acl;
use Espo\Custom\Tools\Fusanhe\OrderService;

final class PostShipmentTransition extends AbstractFusanheAction
{
    public function __construct(
        User $user,
        Acl $acl,
        EntityManager $em,
        private OrderService $service
    ) {
        parent::__construct($user, $acl, $em);
    }

    public function process(Request $request): Response
    {
        $this->requireFeature('orders');
        $this->requireScope('FusanheOrderShipment', 'edit');
        $id = $request->getRouteParam('id');
        $action = (string) $request->getRouteParam('action');
        if (!$id || $action === '') throw new BadRequest();
        return ResponseComposer::json(
            $this->service->shipmentTransition($action, $id, $this->user, $request->getParsedBody())
        );
    }
}
