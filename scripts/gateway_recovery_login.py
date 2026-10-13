"""Serialized browser recovery using native saved-password autofill only."""
from __future__ import annotations

import json
import asyncio
import os
import time
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlsplit

CHANNEL_WORKERS = {"Alibaba": "alibaba", "MadeInChina": "mic"}
HOSTS = {"Alibaba": {"login.alibaba.com", "passport.alibaba.com", "message.alibaba.com"},
         "MadeInChina": {"login.made-in-china.com", "membercenter.made-in-china.com"}}


def directory() -> Path:
    path = Path(os.environ.get("FUSANHE_RECOVERY_DIR", "/srv/gateway/data/recovery"))
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.chmod(0o700)
    return path


def write_json(path: Path, data: dict) -> None:
    temporary = path.with_suffix(".tmp")
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        json.dump(data, stream, ensure_ascii=False)
    temporary.replace(path)
    path.chmod(0o600)


def consume(channel: str) -> dict | None:
    worker = CHANNEL_WORKERS[channel]
    path = directory() / (worker + ".command.json")
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(fd, encoding="utf-8") as stream:
            command = json.load(stream)
        path.unlink()
    except (OSError, ValueError):
        return None
    if command.get("worker") != worker or command.get("action") not in {"auto_login", "retry_sync"}:
        return None
    if not isinstance(command.get("expiresAt"), (int, float)) or not time.time() < command["expiresAt"] <= time.time() + 600:
        return None
    return command


async def wait_filled(field, attempts: int = 30) -> bool:
    # Chromium may paint autofill before exposing it to the form; focus and
    # allow that native operation to settle, without ever reading the value.
    for attempt in range(attempts):
        if await field.evaluate("el => Boolean(el.value)"):
            return True
        if attempt + 1 < attempts:
            await asyncio.sleep(0.1)
    return False


async def saved_login(page, channel: str) -> str:
    """No password value leaves the browser; only filled/not-filled booleans."""
    allowed = HOSTS[channel]
    if urlsplit(page.url).hostname not in allowed:
        return "unexpected_login_host"
    # MIC's /logon.do is the buyer email-first screen. This account is a
    # supplier: use the supplier password screen, retaining only a trusted
    # message-center return URL, never an arbitrary redirect from the page.
    if channel == "MadeInChina" and urlsplit(page.url).path in {"/logon.do", "/sign-in/"} and parse_qs(urlsplit(page.url).query).get("switchLan") != ["1"]:
        destination = parse_qs(urlsplit(page.url).query).get("baseNextPage", [""])[0]
        if urlsplit(destination).hostname != "membercenter.made-in-china.com":
            destination = "https://membercenter.made-in-china.com/message.do"
        await page.goto("https://login.made-in-china.com/sign-in/?" +
                        urlencode({"switchLan": "1", "jumpNext": "1", "baseNextPage": destination}),
                        wait_until="domcontentloaded", timeout=30000)
        if urlsplit(page.url).hostname not in allowed:
            return "unexpected_login_host"
        try:
            await page.locator('input[type="password"]:visible').first.wait_for(state="visible", timeout=15000)
        except Exception:
            pass  # Challenge or mode selection is checked below.
    frames = [f for f in page.frames if urlsplit(f.url).hostname in allowed]
    for frame in frames:
        challenge = frame.locator('iframe[src*="captcha"]:visible, iframe[src*="verify"]:visible, .nc-container:visible, .geetest_panel:visible, input[name*="captcha"]:visible, input[autocomplete="one-time-code"]:visible')
        if await challenge.count():
            return "human_verification_required"
    for frame in frames:
        passwords = frame.locator('input[type="password"]:visible')
        if channel == "MadeInChina" and not await passwords.count():
            mode = frame.get_by_text("密码登录", exact=True)
            if await mode.count() == 1 and await mode.is_visible():
                await mode.click(timeout=10000)
                await passwords.first.wait_for(state="visible", timeout=10000)
        if not await passwords.count():
            continue
        if await passwords.count() != 1:
            return "ambiguous_login_form"
        password = passwords.first
        accounts = frame.locator('input[type="email"]:visible, input[name="loginId"]:visible, input[name="username"]:visible, input[name="logonName"]:visible, #fm-login-id:visible, #account:visible')
        if not await accounts.count():
            accounts = frame.locator('input[autocomplete="username"]:visible, input[type="text"]:visible')
        if await accounts.count() != 1:
            return "ambiguous_login_form"
        # User-authorized native browser autofill. Never read/decrypt Login Data.
        if not await wait_filled(password, 10):
            target = accounts.first if await accounts.count() else password
            await target.click()
            await target.press("ArrowDown")
            await target.press("Enter")
            await password.click()
        if not await wait_filled(password):
            return "saved_password_not_autofilled"
        if not await accounts.count() or not await wait_filled(accounts.first):
            return "saved_account_not_autofilled"
        # Existing login must not accept new contractual terms automatically.
        # Check explicit required consent fields, without toggling any checkbox.
        required_terms = frame.locator('input[type="checkbox"][required]:visible')
        for checkbox in await required_terms.all():
            if not await checkbox.is_checked():
                return "human_consent_required"
        submits = frame.locator('button[type="submit"]:visible, input[type="submit"]:visible, .fm-button:visible')
        if not await submits.count():
            submits = frame.get_by_role("button", name=__import__("re").compile(r"^(登录|登 录|Sign [Ii]n|Log [Ii]n)$"))
        if not await submits.count() and channel == "MadeInChina":
            submits = frame.get_by_text("登录", exact=True).filter(visible=True)
        if await submits.count() != 1:
            return "login_submit_unconfirmed"
        await submits.first.click(timeout=10000)
        # The caller rechecks the authenticated message page; submit is not success.
        return "login_submitted"
    return "login_form_not_available"


async def handle_recovery(page, channel: str) -> str | None:
    if os.environ.get("FUSANHE_RECOVERY_ENABLED") != "true":
        return None
    command = consume(channel)
    if not command:
        return None
    try:
        code = "retry_sync_requested" if command["action"] == "retry_sync" else await saved_login(page, channel)
    except Exception:
        code = "login_browser_operation_failed"
    write_json(directory() / (CHANNEL_WORKERS[channel] + ".result.json"),
               {"nonce": command.get("nonce"), "action": command["action"], "code": code, "at": time.time()})
    return code
