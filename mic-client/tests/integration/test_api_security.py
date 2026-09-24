from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path
from typing import Annotated

import pytest
import pytest_asyncio
from fastapi import Depends, Request
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from mic_gateway.api.auth import Principal, create_api_key, require_role
from mic_gateway.api.middleware import enforce_rate_limit
from mic_gateway.config import Settings
from mic_gateway.db.base import Base, create_engine_and_sessionmaker
from mic_gateway.db.models import ApiKey
from mic_gateway.domain import Role
from mic_gateway.main import create_app

CrmPrincipal = Annotated[Principal, Depends(require_role(Role.CRM_READ))]
AgentPrincipal = Annotated[Principal, Depends(require_role(Role.AGENT_SEND))]


@pytest_asyncio.fixture
async def secured_app(
    tmp_path: Path,
) -> AsyncIterator[tuple[object, async_sessionmaker[AsyncSession], dict[str, str]]]:
    settings = Settings(
        app_data_dir=tmp_path,
        database_url=f"sqlite+aiosqlite:///{(tmp_path / 'security.db').as_posix()}",
        max_request_bytes=65_536,
    )
    engine, sessions = create_engine_and_sessionmaker(settings)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    keys: dict[str, str] = {}
    async with sessions() as session:
        keys["crm"] = await create_api_key(session, "crm", Role.CRM_READ)
        keys["agent"] = await create_api_key(session, "agent", Role.AGENT_SEND)
        keys["admin"] = await create_api_key(session, "admin", Role.ADMIN)
        keys["revoked"] = await create_api_key(session, "revoked", Role.CRM_READ)
        revoked = (
            await session.execute(select(ApiKey).where(ApiKey.name == "revoked"))
        ).scalar_one()
        revoked.revoked = True
        await session.commit()

    app = create_app(settings, session_factory=sessions)

    @app.get("/test/v1/orders/{order_id}")
    async def protected_order(
        order_id: str,
        principal: CrmPrincipal,
    ) -> dict[str, str]:
        return {"id": order_id, "caller": principal.name}

    @app.post("/test/v1/conversations/{conversation_id}/messages")
    async def protected_send(
        conversation_id: str,
        request: Request,
        principal: AgentPrincipal,
    ) -> dict[str, str]:
        await enforce_rate_limit(request, principal, bucket="send", limit=10, window_seconds=60)
        return {"conversation_id": conversation_id}

    yield app, sessions, keys
    await engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize("key_name", [None, "invalid", "revoked"])
async def test_unauthorized_call_does_not_disclose_resource(
    secured_app: tuple[object, async_sessionmaker[AsyncSession], dict[str, str]],
    key_name: str | None,
) -> None:
    app, _, keys = secured_app
    headers = {}
    if key_name == "invalid":
        headers["X-API-Key"] = "invalid"
    elif key_name == "revoked":
        headers["X-API-Key"] = keys["revoked"]

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/test/v1/orders/known-order", headers=headers)

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"
    assert "known-order" not in response.text


@pytest.mark.asyncio
async def test_crm_key_cannot_submit_message(
    secured_app: tuple[object, async_sessionmaker[AsyncSession], dict[str, str]],
) -> None:
    app, _, keys = secured_app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/test/v1/conversations/missing/messages",
            headers={"X-API-Key": keys["crm"]},
            json={"content": "Hello"},
        )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"
    assert "missing" not in response.text


@pytest.mark.asyncio
async def test_send_rate_limit_hides_resource_state(
    secured_app: tuple[object, async_sessionmaker[AsyncSession], dict[str, str]],
) -> None:
    app, _, keys = secured_app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        responses = [
            await client.post(
                    "/test/v1/conversations/missing/messages",
                headers={"X-API-Key": keys["agent"]},
                json={"content": "Hello"},
            )
            for _ in range(11)
        ]

    assert all(response.status_code == 200 for response in responses[:10])
    assert responses[-1].status_code == 429
    assert responses[-1].json()["error"]["code"] == "rate_limited"
    assert "missing" not in responses[-1].text


@pytest.mark.asyncio
async def test_request_id_and_body_limit_are_enforced(
    secured_app: tuple[object, async_sessionmaker[AsyncSession], dict[str, str]],
) -> None:
    app, _, keys = secured_app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        valid = await client.get(
            "/test/v1/orders/order-1",
            headers={"X-API-Key": keys["crm"], "X-Request-ID": "crm.request-1"},
        )
        invalid = await client.get(
            "/test/v1/orders/order-1",
            headers={"X-API-Key": keys["crm"], "X-Request-ID": "not valid!"},
        )
        oversized = await client.post(
            "/test/v1/conversations/c1/messages",
            headers={"X-API-Key": keys["agent"]},
            content=b"x" * 65_537,
        )

    assert valid.headers["X-Request-ID"] == "crm.request-1"
    assert invalid.headers["X-Request-ID"] != "not valid!"
    assert oversized.status_code == 413
    assert oversized.json()["error"]["code"] == "request_too_large"
