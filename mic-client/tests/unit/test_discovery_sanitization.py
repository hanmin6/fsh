from __future__ import annotations

from pathlib import Path

from mic_gateway.browser.discovery import (
    DiscoveryRecorder,
    sanitize_capture,
    sanitize_html,
    sanitize_url,
)


def test_capture_removes_credentials_and_customer_pii() -> None:
    capture = {
        "authorization": "Bearer secret",
        "cookie": "sid=secret",
        "email": "buyer@example.com",
        "phone": "+86 13800138000",
        "buyer_name": "Jane Doe",
        "company": "Example Imports Ltd",
        "address": "1 Buyer Street",
        "userName": "Private User",
        "contactNo": "private-contact-7",
        "contactAvatar": "https://example.test/private.jpg",
        "imgUrl": "https://example.test/catalog/private.jpg",
        "handler": "Private Operator",
        "ip": "203.0.113.8",
        "time": "2026-09-19 10:45:00",
        "formatTime": "2026-09-19 10:45",
        "isContactRead": True,
        "messageContent": "Customer's private inquiry",
        "summer": "Private message summary",
        "msgId": "private-message-id",
        "id": "order-1",
        "nested": {"session_token": "secret", "note": "mail buyer@example.com"},
    }

    result = sanitize_capture(capture)

    assert result == {
        "authorization": "[REDACTED]",
        "cookie": "[REDACTED]",
        "email": "[EMAIL]",
        "phone": "[PHONE]",
        "buyer_name": "Buyer 001",
        "company": "Company 001",
        "address": "Address 001",
        "userName": "Name 001",
        "contactNo": "Contact 001",
        "contactAvatar": "[REDACTED]",
        "imgUrl": "[REDACTED]",
        "handler": "Account 001",
        "ip": "[REDACTED]",
        "time": "2026-09-19 10:45:00",
        "formatTime": "2026-09-19 10:45",
        "isContactRead": True,
        "messageContent": "Message 001",
        "summer": "Message 002",
        "msgId": "Account 002",
        "id": "order-1",
        "nested": {"session_token": "[REDACTED]", "note": "mail [EMAIL]"},
    }


def test_url_keeps_only_origin_and_path() -> None:
    assert sanitize_url(
        "https://seller.example.test/api/orders?token=secret&buyer=1#fragment"
    ) == "https://seller.example.test/api/orders"


def test_html_removes_scripts_pii_and_customer_text() -> None:
    html = """
    <main data-buyer="Jane Doe"><script>secret()</script>
      <input type="hidden" value="csrf-private-value">
      <img alt="Private User" src="https://example.test/photo?id=private">
      <div class="company">Example Imports</div>
      <span>buyer@example.com</span><span>+86 13800138000</span>
    </main>
    """

    result = sanitize_html(html)

    assert "secret" not in result
    assert "Jane Doe" not in result
    assert "Example Imports" not in result
    assert "buyer@example.com" not in result
    assert "13800138000" not in result
    assert "csrf-private-value" not in result
    assert "Private User" not in result
    assert "?id=private" not in result
    assert "[EMAIL]" in result and "[PHONE]" in result


def test_recorder_writes_only_below_application_data(tmp_path: Path) -> None:
    recorder = DiscoveryRecorder(tmp_path, "orders")

    path = recorder.write_capture(
        {
            "method": "GET",
            "url": "https://seller.example.test/api/orders?token=secret",
            "status": 200,
            "content_type": "application/json",
            "body": {"authorization": "secret", "id": "order-1"},
        }
    )

    assert path.is_relative_to(tmp_path / "discovery")
    text = path.read_text(encoding="utf-8")
    assert "token=secret" not in text
    assert "authorization\": \"[REDACTED]" in text


def test_recorder_resanitizes_stale_capture_files(tmp_path: Path) -> None:
    output = tmp_path / "discovery" / "orders"
    output.mkdir(parents=True)
    stale = output / "capture-999.sanitized.json"
    stale.write_text(
        '{"method":"GET","url":"https://example.test?token=x",'
        '"status":200,"content_type":"application/json",'
        '"body":{"userName":"Private User","cookie":"secret"}}',
        encoding="utf-8",
    )

    DiscoveryRecorder(tmp_path, "orders")

    text = stale.read_text(encoding="utf-8")
    assert "Private User" not in text
    assert "secret" not in text
    assert "Name 001" in text
