import importlib.util
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

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
