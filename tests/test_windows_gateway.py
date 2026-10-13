import importlib.util
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timezone

import pytest

spec = importlib.util.spec_from_file_location(
    "windows_gateway", Path(__file__).parents[1] / "scripts/run_windows_gateway.py"
)
gateway = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gateway)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("url", "marker", "expected"),
    [
        ("about:blank", True, "login_required"),
        ("https://passport.alibaba.com/login", True, "login_required"),
        ("https://message.alibaba.com/message/default.htm", False, "message_page_unconfirmed"),
        ("https://message.alibaba.com/message/default.htm", True, "ready"),
    ],
)
async def test_alibaba_requires_positive_message_page(url, marker, expected):
    page = MagicMock()
    page.url = url
    page.is_closed.return_value = False
    page.locator.return_value.count = AsyncMock(return_value=0)
    page.evaluate = AsyncMock(return_value=marker)
    assert await gateway.alibaba_readiness(page) == expected


@pytest.mark.asyncio
async def test_closed_browser_cannot_be_reported_online():
    page = MagicMock()
    page.is_closed.return_value = True
    assert await gateway.alibaba_readiness(page) == "browser_closed"


def test_mic_full_sweep_can_take_minutes_but_stale_or_failed_source_is_blocked():
    now = datetime(2026, 10, 10, 15, 10, tzinfo=timezone.utc)
    sync = {"conversations": {"last_success_at": "2026-10-10T15:03:00Z", "failure_count": 0, "fresh": False}}
    assert gateway.mic_source_ready({"sync": sync}, now)
    sync['messages:one'] = {"failure_count": 1}
    assert not gateway.mic_source_ready({"sync": sync}, now)
    sync['messages:one']['failure_count'] = 0
    sync['conversations']['last_success_at'] = "2026-10-10T14:30:00Z"
    assert not gateway.mic_source_ready({"sync": sync}, now)
    sync['conversations']['last_success_at'] = None
    assert not gateway.mic_source_ready({"sync": sync}, now)
