from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import select

from mic_gateway.api.auth import create_api_key, revoke_api_key, role_allows
from mic_gateway.api.middleware import RateLimiter
from mic_gateway.config import Settings
from mic_gateway.db.base import Base, create_engine_and_sessionmaker
from mic_gateway.db.models import ApiKey
from mic_gateway.domain import Role


@pytest.mark.asyncio
async def test_plaintext_key_is_returned_once_and_only_hash_is_stored(tmp_path: Path) -> None:
    settings = Settings(
        app_data_dir=tmp_path,
        database_url=f"sqlite+aiosqlite:///{(tmp_path / 'auth.db').as_posix()}",
    )
    engine, sessions = create_engine_and_sessionmaker(settings)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with sessions() as session:
        raw = await create_api_key(session, "crm", Role.CRM_READ)
        row = (await session.execute(select(ApiKey).where(ApiKey.name == "crm"))).scalar_one()

    await engine.dispose()
    assert raw.startswith("mic_")
    assert raw not in row.key_hash
    assert row.key_prefix == raw[:12]


@pytest.mark.asyncio
async def test_api_key_can_be_revoked_by_exact_name(tmp_path: Path) -> None:
    settings = Settings(
        app_data_dir=tmp_path,
        database_url=f"sqlite+aiosqlite:///{(tmp_path / 'revoke.db').as_posix()}",
    )
    engine, sessions = create_engine_and_sessionmaker(settings)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with sessions() as session:
        await create_api_key(session, "crm-old", Role.CRM_READ)
        assert await revoke_api_key(session, "crm-old") is True
        assert await revoke_api_key(session, "missing") is False
        row = (
            await session.execute(select(ApiKey).where(ApiKey.name == "crm-old"))
        ).scalar_one()

    await engine.dispose()
    assert row.revoked is True


@pytest.mark.parametrize(
    ("actual", "required", "allowed"),
    [
        (Role.CRM_READ, Role.CRM_READ, True),
        (Role.CRM_READ, Role.AGENT_SEND, False),
        (Role.AGENT_SEND, Role.CRM_READ, True),
        (Role.AGENT_SEND, Role.AGENT_SEND, True),
        (Role.ADMIN, Role.CRM_READ, True),
        (Role.ADMIN, Role.AGENT_SEND, True),
        (Role.ADMIN, Role.ADMIN, True),
    ],
)
def test_role_hierarchy(actual: Role, required: Role, allowed: bool) -> None:
    assert role_allows(actual, (required,)) is allowed


@pytest.mark.asyncio
async def test_rate_limiter_releases_expired_window() -> None:
    now = [100.0]
    limiter = RateLimiter(clock=lambda: now[0])

    assert await limiter.consume("agent:send", limit=2, window_seconds=60) is True
    assert await limiter.consume("agent:send", limit=2, window_seconds=60) is True
    assert await limiter.consume("agent:send", limit=2, window_seconds=60) is False

    now[0] = 161.0
    assert await limiter.consume("agent:send", limit=2, window_seconds=60) is True
