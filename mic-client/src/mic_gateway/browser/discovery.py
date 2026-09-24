from __future__ import annotations

import asyncio
import json
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from mic_gateway.browser.runtime import BrowserRuntime
from mic_gateway.config import Settings

_SECRET_PARTS = ("authorization", "cookie", "password", "session", "token", "secret")
_EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE)
_PHONE_RE = re.compile(r"(?<!\w)(?:\+?\d[\d\s().-]{8,}\d)(?!\w)")


def sanitize_url(value: str) -> str:
    parsed = urlsplit(value)
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))


def sanitize_capture(value: Any) -> Any:
    counters: dict[str, dict[str, str]] = {
        "buyer": {},
        "company": {},
        "address": {},
        "name": {},
        "account": {},
        "contact": {},
        "message": {},
    }

    def synthetic(category: str, raw: object) -> str:
        key = str(raw)
        values = counters[category]
        if key not in values:
            values[key] = f"{category.title()} {len(values) + 1:03d}"
        return values[key]

    def scrub(item: Any, key: str | None = None) -> Any:
        folded = key.casefold() if key is not None else ""
        if key is not None and any(part in folded for part in _SECRET_PARTS):
            return "[REDACTED]"
        if key is not None and "email" in folded:
            return "[EMAIL]"
        if key is not None and ("phone" in folded or "mobile" in folded):
            return "[PHONE]"
        if key is not None and any(
            part in folded
            for part in ("avatar", "photo", "portrait", "image", "img")
        ):
            return "[REDACTED]"
        if key is not None and folded == "ip":
            return "[REDACTED]"
        if key is not None and isinstance(item, str) and any(
            part in folded for part in ("time", "date", "timestamp")
        ):
            return _EMAIL_RE.sub("[EMAIL]", item)
        if key is not None and "buyer" in folded:
            return synthetic("buyer", item)
        if key is not None and "company" in folded:
            return synthetic("company", item)
        if key is not None and "address" in folded:
            return synthetic("address", item)
        if key is not None and "account" in folded:
            return synthetic("account", item)
        if key is not None and "name" in folded:
            return synthetic("name", item)
        if key is not None and folded in {"handler", "operator", "assignee"}:
            if isinstance(item, bool) or item is None:
                return item
            return synthetic("account", item)
        if key is not None and "user" in folded and not isinstance(item, (dict, list, tuple)):
            if isinstance(item, bool) or item is None:
                return item
            return synthetic("account", item)
        if key is not None and "contact" in folded and not isinstance(
            item, (dict, list, tuple)
        ):
            if isinstance(item, bool) or item is None or "read" in folded:
                return item
            return synthetic("contact", item)
        if key is not None and folded != "id" and (
            folded.endswith("id") or folded.endswith("no")
        ) and not isinstance(item, (dict, list, tuple)):
            if isinstance(item, bool) or item is None:
                return item
            return synthetic("account", item)
        if key is not None and any(
            part in folded
            for part in (
                "content",
                "message",
                "subject",
                "title",
                "text",
                "summary",
                "summer",
                "remark",
                "description",
                "question",
                "reply",
            )
        ) and not isinstance(item, (dict, list, tuple)):
            if isinstance(item, str):
                return synthetic("message", item)
            return item
        if isinstance(item, dict):
            return {
                str(child_key): scrub(child, str(child_key))
                for child_key, child in item.items()
            }
        if isinstance(item, (list, tuple)):
            return [scrub(child) for child in item]
        if isinstance(item, str):
            scrubbed = _PHONE_RE.sub("[PHONE]", _EMAIL_RE.sub("[EMAIL]", item))
            if re.search(r"https?://|www\.", scrubbed, re.IGNORECASE):
                return "[URL]"
            return scrubbed
        return item

    return scrub(value)


def sanitize_html(value: str) -> str:
    result = re.sub(
        r"<(script|style)\b[^>]*>.*?</\1\s*>",
        "",
        value,
        flags=re.IGNORECASE | re.DOTALL,
    )
    result = re.sub(
        r"((?:data-)?(?:buyer|company|address|email|phone|mobile)\s*=\s*)([\"']).*?\2",
        lambda match: f'{match.group(1)}{match.group(2)}[REDACTED]{match.group(2)}',
        result,
        flags=re.IGNORECASE,
    )
    result = re.sub(
        r"\s(value|alt|title|content|data-[\w:-]+)\s*=\s*([\"']).*?\2",
        lambda match: f' {match.group(1)}={match.group(2)}[REDACTED]{match.group(2)}',
        result,
        flags=re.IGNORECASE | re.DOTALL,
    )

    def clean_url_attribute(match: re.Match[str]) -> str:
        return f' {match.group(1)}={match.group(2)}{sanitize_url(match.group(3))}{match.group(2)}'

    result = re.sub(
        r"\s(href|src)\s*=\s*([\"'])(.*?)\2",
        clean_url_attribute,
        result,
        flags=re.IGNORECASE | re.DOTALL,
    )

    def replace_text(match: re.Match[str]) -> str:
        text = match.group(1)
        if not text.strip():
            return f">{text}<"
        scrubbed = _PHONE_RE.sub("[PHONE]", _EMAIL_RE.sub("[EMAIL]", text))
        if scrubbed == text:
            scrubbed = "[TEXT]"
        return f">{scrubbed}<"

    result = re.sub(r">([^<>]+)<", replace_text, result)
    return _PHONE_RE.sub("[PHONE]", _EMAIL_RE.sub("[EMAIL]", result))


class DiscoveryRecorder:
    def __init__(self, app_data_dir: Path, resource: str) -> None:
        if resource not in {"orders", "conversations", "messages"}:
            raise ValueError("unsupported discovery resource")
        self.resource = resource
        self.output_dir = app_data_dir.resolve() / "discovery" / resource
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._sequence = 0
        self._tasks: set[asyncio.Task[None]] = set()
        self.resanitize_existing()

    @staticmethod
    def _clean_capture(capture: dict[str, Any]) -> dict[str, Any]:
        return {
            "method": str(capture.get("method", "GET")),
            "url": sanitize_url(str(capture.get("url", ""))),
            "status": int(capture.get("status", 0)),
            "content_type": str(capture.get("content_type", "")),
            "body": sanitize_capture(capture.get("body")),
        }

    def resanitize_existing(self) -> None:
        for path in self.output_dir.glob("*.json"):
            try:
                capture = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(capture, dict):
                path.write_text(
                    json.dumps(
                        self._clean_capture(capture),
                        ensure_ascii=False,
                        indent=2,
                        default=str,
                    ),
                    encoding="utf-8",
                )
        for path in self.output_dir.glob("*.html"):
            path.write_text(
                sanitize_html(path.read_text(encoding="utf-8")),
                encoding="utf-8",
            )

    def write_capture(self, capture: dict[str, Any]) -> Path:
        self._sequence += 1
        cleaned = self._clean_capture(capture)
        path = self.output_dir / f"capture-{self._sequence:03d}.sanitized.json"
        path.write_text(
            json.dumps(cleaned, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
        return path

    async def capture_response(self, response: Any) -> None:
        path = urlsplit(response.url).path.casefold()
        keywords = {
            "orders": ("order",),
            "conversations": ("conversation", "inquiry", "message"),
            "messages": ("conversation", "inquiry", "message"),
        }[self.resource]
        if not any(keyword in path for keyword in keywords):
            return
        content_type = str(response.headers.get("content-type", ""))
        if "json" not in content_type.casefold():
            return
        try:
            body = await response.json()
        except Exception:
            return
        self.write_capture(
            {
                "method": response.request.method,
                "url": response.url,
                "status": response.status,
                "content_type": content_type,
                "body": body,
            }
        )

    def observe(self, page: Any) -> None:
        def schedule(response: Any) -> None:
            task = asyncio.create_task(self.capture_response(response))
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)

        page.on("response", schedule)

    async def finish(self) -> None:
        if self._tasks:
            await asyncio.gather(*tuple(self._tasks))

    def write_html(self, html: str) -> Path:
        path = self.output_dir / "page.sanitized.html"
        path.write_text(sanitize_html(html), encoding="utf-8")
        return path


async def discover_resource(
    settings: Settings,
    resource: str,
    *,
    confirm: Callable[[str], str] = input,
) -> list[Path]:
    recorder = DiscoveryRecorder(settings.app_data_dir, resource)
    runtime = BrowserRuntime(settings.model_copy(update={"chromium_headless": False}))
    await runtime.start()
    try:
        async def prepare(page: Any) -> None:
            recorder.observe(page)
            await page.goto(settings.seller_url)

        await runtime.run_serialized(prepare)
        await asyncio.to_thread(
            confirm,
            f"Open the {resource} page and perform one read-only navigation, then press Enter: ",
        )
        html = await runtime.run_serialized(
            lambda page: page.locator("main, [role='main'], body").first.inner_html()
        )
        html_path = recorder.write_html(html)
        await recorder.finish()
        return [*sorted(recorder.output_dir.glob("*.json")), html_path]
    finally:
        await runtime.stop()
