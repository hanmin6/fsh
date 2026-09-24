from __future__ import annotations

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--live",
        action="store_true",
        default=False,
        help="run read-only tests against the authenticated seller profile",
    )
    parser.addoption(
        "--live-send",
        action="store_true",
        default=False,
        help="send one message to the explicitly configured test conversation",
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    live_enabled = bool(config.getoption("--live"))
    live_send_enabled = bool(config.getoption("--live-send"))
    skip_live = pytest.mark.skip(reason="requires --live")
    skip_live_send = pytest.mark.skip(reason="requires --live-send")
    for item in items:
        if "live_send" in item.keywords and not live_send_enabled:
            item.add_marker(skip_live_send)
        elif "live" in item.keywords and not live_enabled:
            item.add_marker(skip_live)
