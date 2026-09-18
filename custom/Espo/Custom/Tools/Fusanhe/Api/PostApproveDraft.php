<?php
namespace Espo\Custom\Tools\Fusanhe\Api;

use Espo\Core\Api\Action;
use Espo\Core\Api\Request;
use Espo\Core\Api\Response;
use Espo\Core\Api\ResponseComposer;
use Espo\Custom\Tools\Fusanhe\WorkflowService;
use Espo\Core\Exceptions\BadRequest;
use Espo\Entities\User;
use Espo\Core\Acl;
use Espo\Core\Exceptions\Forbidden;
final class PostApproveDraft implements Action { public function __construct(private WorkflowService $service, private User $user, private Acl $acl) {} public function process(Request $request): Response { if (!$this->user->isAdmin() && !$this->acl->checkScope('OutboundTask', 'create')) throw new Forbidden('Not allowed to approve outbound messages.'); $id=$request->getRouteParam('id');if(!$id)throw new BadRequest();$b=$request->getParsedBody();return ResponseComposer::json($this->service->approve($id,$this->user,isset($b->draftText)?(string)$b->draftText:null)); } }
