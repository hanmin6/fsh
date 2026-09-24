from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from mic_gateway.adapters.base import SessionHealth
from mic_gateway.api.auth import create_api_key
from mic_gateway.config import Settings
from mic_gateway.db.base import Base, create_engine_and_sessionmaker
from mic_gateway.db.repositories import CheckpointRepository
from mic_gateway.domain import Role
from mic_gateway.main import create_app
from mic_gateway.monitoring.status import StatusService


class SchedulerStub:
    def __init__(self) -> None:
        self.commands: set[str] = set()

    def queue_manual_sync(self, resource: str) -> bool:
        before = len(self.commands)
        self.commands.add(resource)
        return len(self.commands) > before


@pytest_asyncio.fixture
async def status_api(tmp_path: Path) -> Any:
    settings = Settings(
        app_data_dir=tmp_path,
        database_url=f"sqlite+aiosqlite:///{(tmp_path / 'status.db').as_posix()}",
    )
    engine, sessions = create_engine_and_sessionmaker(settings)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with sessions() as session:
        crm = await create_api_key(session, "crm", Role.CRM_READ)
        admin = await create_api_key(session, "admin", Role.ADMIN)
    service = StatusService(sessions, settings=settings)
    service.set_session_health(SessionHealth.available())
    scheduler = SchedulerStub()
    app = create_app(
        settings,
        session_factory=sessions,
        status_service=service,
        scheduler=cast(Any, scheduler),
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client, sessions, service, scheduler, crm, admin
    await engine.dispose()


@pytest.mark.asyncio
async def test_stale_sync_is_degraded_and_status_is_safe(status_api: Any) -> None:
    client, sessions, _, _, crm, _ = status_api
    now = datetime.now(UTC)
    await CheckpointRepository(sessions).save(
        "conversations",
        last_attempt_at=now - timedelta(seconds=121),
        last_success_at=now - timedelta(seconds=121),
    )
    response = await client.get("/v1/status", headers={"X-API-Key": crm})

    assert response.status_code == 200
    assert response.json()["state"] == "degraded"
    assert response.json()["sync"]["conversations"]["fresh"] is False
    assert "browser-profile" not in response.text
    assert "cookie" not in response.text.casefold()


@pytest.mark.asyncio
async def test_operator_action_state_and_admin_sync_deduplicate(status_api: Any) -> None:
    client, _, service, scheduler, crm, admin = status_api
    service.set_session_health(SessionHealth.verification_required())
    status = await client.get("/v1/status", headers={"X-API-Key": crm})
    first = await client.post(
        "/v1/admin/sync", headers={"X-API-Key": admin}, json={"resource": "orders"}
    )
    second = await client.post(
        "/v1/admin/sync", headers={"X-API-Key": admin}, json={"resource": "orders"}
    )

    assert status.json()["state"] == "operator_action_required"
    assert first.status_code == 202 and first.json()["queued"] is True
    assert second.status_code == 202 and second.json()["queued"] is False
    assert scheduler.commands == {"orders"}


@pytest.mark.asyncio
async def test_readiness_fails_when_database_is_unavailable(tmp_path: Path) -> None:
    settings = Settings(app_data_dir=tmp_path)

    class BrokenSessions:
        def __call__(self) -> Any:
            raise RuntimeError("database unavailable")

    app = create_app(
        settings,
        session_factory=cast(async_sessionmaker[AsyncSession], BrokenSessions()),
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {"status": "not_ready", "code": "database_unavailable"}
