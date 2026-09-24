from __future__ import annotations

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from mic_gateway.config import Settings
from mic_gateway.main import create_app


@pytest.mark.asyncio
async def test_liveness_needs_no_api_key(tmp_path: Path) -> None:
    app = create_app(Settings(app_data_dir=tmp_path))

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "alive"}
