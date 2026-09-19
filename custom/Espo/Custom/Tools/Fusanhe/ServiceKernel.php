<?php
namespace Espo\Custom\Tools\Fusanhe;

use Espo\ORM\Entity;
use Espo\ORM\EntityManager;

/**
 * Shared persistence and audit kernel for Fusanhe service actions.
 *
 * Every service-level write passes the fusanheService save option so the
 * state-machine hooks can distinguish audited service writes from plain
 * record CRUD. Keeping it in one place also avoids service-to-service
 * constructor cycles.
 */
final class ServiceKernel
{
    public function __construct(private EntityManager $em) {}

    public function save(Entity $entity, array $extraOptions = []): void
    {
        $this->em->saveEntity($entity, array_merge(['fusanheService' => true], $extraOptions));
    }

    public function create(string $type, array $values): Entity
    {
        $entity = $this->em->getNewEntity($type);
        $entity->set($values);
        $this->save($entity);
        return $entity;
    }

    public function audit(
        string $event,
        string $actorType,
        string $actorId,
        string $entityType,
        string $entityId,
        string $result = 'success',
        array $details = [],
    ): void {
        $this->create('AutomationAudit', [
            'name' => $event . ' ' . gmdate('H:i:s'),
            'eventType' => $event,
            'actorType' => $actorType,
            'actorId' => $actorId !== '' ? $actorId : 'system',
            'entityType' => $entityType,
            'entityId' => $entityId,
            'result' => $result,
            'details' => $details,
        ]);
    }

    public function repo(string $type)
    {
        return $this->em->getRDBRepository($type);
    }

    public function em(): EntityManager
    {
        return $this->em;
    }

    public function now(): string
    {
        return gmdate('Y-m-d H:i:s');
    }
}
