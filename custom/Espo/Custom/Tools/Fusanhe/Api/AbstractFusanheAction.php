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

    /**
     * Entity-level check: own/team roles may only operate on records assigned
     * to them, so scope permission alone is never enough for id-based routes.
     */
    protected function requireEntityScope(string $type, string $id, string $action): \Espo\ORM\Entity
    {
        $this->requireScope($type, $action === 'read' ? 'read' : $action);
        $entity = $this->requireEntity($type, $id);
        if (!$this->user->isAdmin() && !$this->acl->checkEntity($entity, $action)) {
            throw new Forbidden("Not allowed to {$action} this {$type} record.");
        }
        return $entity;
    }

    protected function requireEntity(string $type, string $id): \Espo\ORM\Entity
    {
        $entity = $this->em->getEntityById($type, $id);
        if (!$entity) throw new NotFound("{$type} not found.");
        return $entity;
    }

    /** Correlation id accepted only in a conservative format to prevent log injection. */
    protected function requestId(Request $request): string
    {
        $incoming = trim((string) ($request->getHeader('X-Request-Id') ?? ''));
        if ($incoming !== '' && preg_match('/^[A-Za-z0-9][A-Za-z0-9._:-]{0,63}$/', $incoming)) {
            return $incoming;
        }
        return bin2hex(random_bytes(16));
    }

    /** Successful custom responses always expose the same correlation id. */
    protected function json(Request $request, array $payload, int $status = 200): Response
    {
        $requestId = $this->requestId($request);
        $response = ResponseComposer::json(['requestId' => $requestId] + $payload);
        $response->setStatus($status);
        $response->setHeader('X-Request-Id', $requestId);
        return $response;
    }

    /** Stable, non-sensitive public error codes for API clients and support. */
    protected function errorCode(\Throwable $error): string
    {
        return match (true) {
            $error instanceof BadRequest => 'invalid_request',
            $error instanceof Forbidden => 'forbidden',
            $error instanceof NotFound => 'not_found',
            default => 'internal_error',
        };
    }
}
