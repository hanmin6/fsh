from __future__ import annotations

import json
from pathlib import Path

import pytest

from mic_gateway.adapters.made_in_china.adapter import SiteContractError, parse_orders

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> dict[str, object]:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_observed_empty_order_page_is_validated() -> None:
    result = parse_orders(load_fixture("orders-page.sanitized.json"))

    assert result.items == ()
    assert result.next_cursor is None


def test_unreviewed_nonempty_order_shape_fails_closed() -> None:
    fixture = load_fixture("orders-page.sanitized.json")
    fixture["body"]["content"]["items"] = [{"id": "order-001"}]  # type: ignore[index]

    with pytest.raises(SiteContractError, match="order_list_nonempty_unreviewed"):
        parse_orders(fixture)


def test_incompatible_order_shape_fails_closed() -> None:
    with pytest.raises(SiteContractError, match="order_list"):
        parse_orders({"unexpected": []})
