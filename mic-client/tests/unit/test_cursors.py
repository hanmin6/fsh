from __future__ import annotations

import base64
import json
from datetime import UTC, datetime
from uuid import UUID

import pytest

from mic_gateway.db.repositories import decode_cursor, encode_cursor
from mic_gateway.errors import ApiError


def test_cursor_round_trip_preserves_utc_timestamp_and_uuid() -> None:
    updated_at = datetime(2026, 9, 19, 12, 30, tzinfo=UTC)
    row_id = UUID("12345678-1234-5678-1234-567812345678")

    cursor = encode_cursor(updated_at, row_id)

    assert decode_cursor(cursor) == (updated_at, row_id)


@pytest.mark.parametrize(
    "cursor",
    [
        "not-base64-json",
        base64.urlsafe_b64encode(b"[]").decode().rstrip("="),
        base64.urlsafe_b64encode(json.dumps({"u": "2026-09-19T12:00:00", "i": "bad"}).encode())
        .decode()
        .rstrip("="),
        base64.urlsafe_b64encode(
            json.dumps(
                {
                    "u": "2026-09-19T12:00:00+00:00",
                    "i": "12345678-1234-5678-1234-567812345678",
                    "extra": True,
                }
            ).encode()
        )
        .decode()
        .rstrip("="),
    ],
)
def test_malformed_cursor_is_a_client_error(cursor: str) -> None:
    with pytest.raises(ApiError) as exc:
        decode_cursor(cursor)

    assert exc.value.status_code == 422
    assert exc.value.code == "invalid_cursor"
