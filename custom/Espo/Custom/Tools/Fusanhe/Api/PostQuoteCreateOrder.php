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

final class PostQuoteCreateOrder extends AbstractFusanheAction
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
        if (!$this->user->isAdmin() && (!$this->acl->checkScope('FusanheSalesOrder', 'create') || !$this->acl->checkScope('FusanheQuote', 'read'))) {
            throw new \Espo\Core\Exceptions\Forbidden('Not allowed to create orders from quotes.');
        }
        $id = $request->getRouteParam('id');
        if (!$id) throw new BadRequest();
        $this->requireEntityScope('FusanheQuote', $id, 'read');
        return ResponseComposer::json(
            $this->service->createFromQuote($id, $this->user, $request->getParsedBody())
        );
    }
}
