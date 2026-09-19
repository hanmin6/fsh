<?php
namespace Espo\Custom\Tools\Fusanhe\Api;

use Espo\Core\Api\Action;
use Espo\Core\Api\Request;
use Espo\Core\Api\Response;
use Espo\Core\Api\ResponseComposer;
use Espo\Core\Acl;
use Espo\Core\Exceptions\BadRequest;
use Espo\Core\Exceptions\Forbidden;
use Espo\Core\Exceptions\NotFound;
use Espo\Entities\User;
use Espo\ORM\EntityManager;
use Espo\Custom\Tools\Fusanhe\Features;

/**
 * Shared helpers for industry-module endpoints: feature flag gate, ACL gate,
 * spec review transitions. Kept small on purpose; no plugin platform.
 */
abstract class AbstractFusanheAction implements Action
{
    public function __construct(
        protected User $user,
        protected Acl $acl,
        protected EntityManager $em
    ) {}

    protected function requireFeature(string $feature): void
    {
        if (!Features::enabled($feature)) {
            throw new NotFound('Feature is not enabled.');
        }
    }

    protected function requireScope(string $scope, string $action): void
    {
        if (!$this->user->isAdmin() && !$this->acl->checkScope($scope, $action)) {
            throw new Forbidden("Not allowed to {$action} {$scope}.");
        }
    }

    protected function requireEntity(string $type, string $id): \Espo\ORM\Entity
    {
        $entity = $this->em->getEntityById($type, $id);
        if (!$entity) throw new NotFound("{$type} not found.");
        return $entity;
    }
}
