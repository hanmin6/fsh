<?php
namespace Espo\Custom\Authentication;

use Espo\Core\Api\Request;
use Espo\Core\Authentication\Login;
use Espo\Core\Authentication\Login\Data;
use Espo\Core\Authentication\Logins\Espo;
use Espo\Core\Authentication\Result;
use Espo\Core\Authentication\Result\FailReason;
use Espo\Core\ORM\EntityManagerProxy;
use Espo\Core\Utils\Config;
use Espo\Entities\User;

/** Explicit public workspace entry; normal credentials and tokens keep native validation. */
class Workspace implements Login
{
    public function __construct(
        private Espo $nativeLogin,
        private EntityManagerProxy $entityManager,
        private Config $config,
    ) {}

    public function login(Data $data, Request $request): Result
    {
        if ($data->getUsername() !== '**workspace' || $data->getAuthToken()) {
            return $this->nativeLogin->login($data, $request);
        }
        if (!filter_var(getenv('FUSANHE_PUBLIC_WORKSPACE_ENABLED') ?: 'false', FILTER_VALIDATE_BOOLEAN)) {
            return Result::fail(FailReason::DENIED);
        }
        if ($this->config->get('authenticationMethod') !== 'FusanheWorkspace' ||
            $data->getPassword() !== 'public-workspace') {
            return Result::fail(FailReason::DENIED);
        }
        $id = $this->config->get('fusanheWorkspaceUserId');
        $user = $id ? $this->entityManager->getEntityById(User::ENTITY_TYPE, $id) : null;
        // Never fall back to an administrator or select a caller-provided identity.
        if (!$user || !$user->isRegular() || $user->isAdmin() || !$user->isActive()) {
            return Result::fail(FailReason::DENIED);
        }
        return Result::success($user);
    }
}
