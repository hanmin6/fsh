<?php
namespace Espo\Custom\Tools\Fusanhe\Api;
use Espo\Core\Acl;
use Espo\Entities\User;
use Espo\ORM\EntityManager;
use Espo\Custom\Tools\Fusanhe\SalesService;
abstract class SalesApi extends AbstractFusanheAction
{
    public function __construct(User $user,Acl $acl,EntityManager $em,protected SalesService $sales) {parent::__construct($user,$acl,$em);}
    protected function admin(): void {if (!$this->user->isAdmin())throw new \Espo\Core\Exceptions\Forbidden('Only administrators may change sales settings and approve public facts.');}
}
