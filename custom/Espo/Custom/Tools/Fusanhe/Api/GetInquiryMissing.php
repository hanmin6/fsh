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

final class GetInquiryMissing extends AbstractFusanheAction
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
        $this->requireScope('FusanheInquiry', 'read');
        $id = $request->getRouteParam('id');
        if (!$id) throw new BadRequest();
        return ResponseComposer::json($this->service->inquiryMissing($id));
    }
}
