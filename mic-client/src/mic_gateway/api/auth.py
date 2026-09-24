from __future__ import annotations

import secrets
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, VerifyMismatchError
from fastapi import Depends, Header, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mic_gateway.db.models import ApiKey
from mic_gateway.domain import Role
from mic_gateway.errors import ApiError

_PASSWORD_HASHER = PasswordHasher()
_ROLE_RANK = {Role.CRM_READ: 0, Role.AGENT_SEND: 1, Role.ADMIN: 2}


@dataclass(frozen=True, slots=True)
class Principal:
    key_id: UUID
    name: str
    role: Role


async def create_api_key(session: AsyncSession, name: str, role: Role) -> str:
    raw_key = f"mic_{secrets.token_urlsafe(32)}"
    row = ApiKey(
        name=name,
        key_prefix=raw_key[:12],
        key_hash=_PASSWORD_HASHER.hash(raw_key),
        role=role.value,
        revoked=False,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return raw_key


async def revoke_api_key(session: AsyncSession, name: str) -> bool:
    row = await session.scalar(select(ApiKey).where(ApiKey.name == name))
    if row is None or row.revoked:
        return False
    row.revoked = True
    await session.commit()
    return True


def role_allows(actual: Role, required: tuple[Role, ...]) -> bool:
    actual_rank = _ROLE_RANK[actual]
    return any(actual_rank >= _ROLE_RANK[role] for role in required)


async def authenticate(
    request: Request,
    api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> Principal:
    if api_key is None or not api_key.startswith("mic_"):
        raise ApiError(401, "unauthorized", "A valid API key is required")

    prefix = api_key[:12]
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        candidates = (
            await session.execute(
                select(ApiKey).where(ApiKey.key_prefix == prefix, ApiKey.revoked.is_(False))
            )
        ).scalars()
        for candidate in candidates:
            try:
                if _PASSWORD_HASHER.verify(candidate.key_hash, api_key):
                    return Principal(
                        key_id=candidate.id,
                        name=candidate.name,
                        role=Role(candidate.role),
                    )
            except (VerifyMismatchError, VerificationError):
                continue

    raise ApiError(401, "unauthorized", "A valid API key is required")


def require_role(*allowed: Role) -> Callable[..., Awaitable[Principal]]:
    async def dependency(
        principal: Annotated[Principal, Depends(authenticate)],
    ) -> Principal:
        if not role_allows(principal.role, allowed):
            raise ApiError(403, "forbidden", "The API key lacks this permission")
        return principal

    return dependency
