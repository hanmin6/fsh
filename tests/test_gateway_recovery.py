"""Recovery tests never use real saved credentials or send customer messages."""
import importlib.util
import json
import sys
import time
import io
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

SCRIPTS = Path(__file__).parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import gateway_recovery_login as login
import gateway_recovery_agent as recovery


def test_expired_and_wrong_worker_commands_cannot_drive_browser(tmp_path, monkeypatch):
    monkeypatch.setenv("FUSANHE_RECOVERY_DIR", str(tmp_path))
    for data in [{"worker": "mic", "action": "auto_login", "expiresAt": time.time() - 1},
                 {"worker": "alibaba", "action": "auto_login", "expiresAt": time.time() + 30},
                 {"worker": "mic", "action": "send_message", "expiresAt": time.time() + 30}]:
        login.write_json(tmp_path / "mic.command.json", data)
        assert login.consume("MadeInChina") is None


def test_valid_recovery_command_is_consumed_once(tmp_path, monkeypatch):
    monkeypatch.setenv("FUSANHE_RECOVERY_DIR", str(tmp_path))
    login.write_json(tmp_path / "mic.command.json", {"worker": "mic", "action": "auto_login", "nonce": "fixture", "expiresAt": time.time() + 30})
    assert login.consume("MadeInChina")["nonce"] == "fixture"
    assert login.consume("MadeInChina") is None


@pytest.mark.asyncio
async def test_login_never_interacts_with_unapproved_origin():
    page = MagicMock(url="https://attacker.invalid/login")
    assert await login.saved_login(page, "MadeInChina") == "unexpected_login_host"
    page.locator.assert_not_called()


@pytest.mark.asyncio
async def test_delayed_native_autofill_is_confirmed_using_only_booleans(monkeypatch):
    monkeypatch.setattr(login.asyncio, "sleep", AsyncMock())
    field = MagicMock()
    field.evaluate = AsyncMock(side_effect=[False, False, True])
    assert await login.wait_filled(field)
    field.input_value.assert_not_called()
    assert all(call.args == ("el => Boolean(el.value)",) for call in field.evaluate.call_args_list)


@pytest.mark.asyncio
async def test_verification_is_handed_to_human_before_password_submit():
    frame = MagicMock(url="https://login.alibaba.com/")
    frame.locator.return_value.count = AsyncMock(return_value=1)
    page = MagicMock(url=frame.url, frames=[frame])
    assert await login.saved_login(page, "Alibaba") == "human_verification_required"
    frame.locator.return_value.click.assert_not_called()


@pytest.mark.asyncio
async def test_prefilled_login_submits_without_reading_password_value():
    password = MagicMock()
    password.evaluate = AsyncMock(return_value=True)
    account = MagicMock()
    account.evaluate = AsyncMock(return_value=True)
    submit = MagicMock()
    submit.click = AsyncMock()
    frame = MagicMock(url="https://login.made-in-china.com/")
    def locator(selector):
        group = MagicMock()
        if 'input[type="password"]' in selector:
            group.count = AsyncMock(return_value=1)
            group.first = password
        elif 'input[type="email"]' in selector:
            group.count = AsyncMock(return_value=1)
            group.first = account
        elif 'button[type="submit"]' in selector:
            group.count = AsyncMock(return_value=1)
            group.first = submit
        else:
            group.count = AsyncMock(return_value=0)
            group.all = AsyncMock(return_value=[])
        return group
    frame.locator.side_effect = locator
    page = MagicMock(url=frame.url, frames=[frame])
    assert await login.saved_login(page, "MadeInChina") == "login_submitted"
    submit.click.assert_awaited_once()
    password.input_value.assert_not_called()
    account.input_value.assert_not_called()
    assert all("Boolean(el.value)" in call.args[0] for call in password.evaluate.call_args_list)


@pytest.mark.asyncio
async def test_mic_buyer_screen_switches_to_supplier_without_untrusted_redirect():
    frame = MagicMock(url="https://login.made-in-china.com/sign-in/")
    frame.locator.return_value.count = AsyncMock(return_value=1)
    page = MagicMock(url="https://login.made-in-china.com/logon.do?baseNextPage=https%3A%2F%2Fattacker.invalid", frames=[frame])
    page.goto = AsyncMock()
    page.locator.return_value.first.wait_for = AsyncMock()
    assert await login.saved_login(page, "MadeInChina") == "human_verification_required"
    destination = page.goto.call_args.args[0]
    assert destination.startswith("https://login.made-in-china.com/sign-in/?")
    assert "attacker" not in destination
    assert "membercenter.made-in-china.com" in destination
    assert "switchLan=1" in destination


def test_supervisor_cannot_restart_unrelated_services():
    with pytest.raises(ValueError):
        recovery.RecoveryAgent.supervisor("start", "crm-database")
    with pytest.raises(ValueError):
        recovery.RecoveryAgent.supervisor("shell", "mic")


def test_real_source_age_wins_over_fresh_crm_bridge_time(monkeypatch):
    monkeypatch.setattr(recovery, "age", lambda value: 4000 if value == "old" else 1)
    status = {"sync": {"conversations": {"last_success_at": "old", "last_attempt_at": "new", "failure_count": 1}}}
    assert recovery.source_health(status, 10) == (4000, False, False)


def test_active_sweep_is_not_stalled_but_missing_worker_is(monkeypatch):
    monkeypatch.setattr(recovery, "age", lambda value: 5)
    workers = [{"name": "mic-"+n, "done": False, "steps": ["sync_conversations_and_messages"] if n=='conversations' else []}
               for n in ['health','conversations','orders','outbox']]
    status = {'sync': {'conversations': {'last_success_at': 'recent'}},
              'poller': {'locked': True, 'workers': workers}}
    assert recovery.source_health(status, 10) == (10, True, False)
    workers[1]['done'] = True
    assert recovery.source_health(status, 10) == (10, False, True)


def test_hung_lock_without_progress_is_restartable(monkeypatch):
    monkeypatch.setattr(recovery, "age", lambda value: 1200)
    workers = [{"name": 'mic-'+n, 'done': False, 'steps': ['sync_conversations_and_messages']}
               for n in ['health','conversations','orders','outbox']]
    status = {'sync': {'conversations': {'last_success_at': 'old'}},
              'poller': {'locked': True, 'workers': workers}}
    assert recovery.source_health(status, 10) == (1200, False, True)


def test_idle_authenticated_unconsumed_command_recovers_without_model(tmp_path, monkeypatch):
    monkeypatch.setenv('FUSANHE_RECOVERY_DIR', str(tmp_path))
    agent = recovery.RecoveryAgent({}, {})
    agent.heartbeat = lambda: None
    agent.state['workers']['mic'] = {'commandNonce': 'hung', 'commandAt': time.time()-301}
    observation = {'worker':'mic','processRunning':True,'sessionState':'healthy','sourceAgeSeconds':4000,
                   'sourceBusy':False,'pending':False,'hasReplayPayload':False,'autoLoginSupported':True,'reasonCode':'source_stale'}
    agent.observe = lambda worker: observation if worker=='mic' else {'worker':worker,'reasonCode':'healthy'}
    agent.request = lambda *a, **k: pytest.fail('routine hung-command recovery must not invoke model')
    actions = []
    agent.act = lambda worker, action: actions.append((worker,action)) or 'worker_started'
    agent.record = lambda *a: None
    agent.once()
    assert actions == [('mic','restart_worker')]
    assert 'blockedSignature' not in agent.state['workers']['mic']


def test_busy_source_keeps_recovery_plan_from_restarting_browser(tmp_path, monkeypatch):
    monkeypatch.setenv("FUSANHE_RECOVERY_DIR", str(tmp_path))
    agent = recovery.RecoveryAgent({}, {})
    agent.heartbeat = lambda: None
    observation = {"worker": "mic", "processRunning": True, "sessionState": "unavailable", "sourceAgeSeconds": 2000, "sourceBusy": True, "pending": False, "hasReplayPayload": False, "autoLoginSupported": True, "reasonCode": "browser_unavailable"}
    agent.observe = lambda worker: dict(observation, worker=worker)
    agent.request = lambda worker, operation, **kw: {"model": recovery.MODEL, "action": "restart_worker"}
    actions = []
    agent.act = lambda worker, action: actions.append(action) or "observing"
    agent.record = lambda *args: None
    agent.once(smoke=True)
    assert actions and set(actions) == {"wait"}


def test_recovered_session_does_not_poison_next_login_expiration(tmp_path, monkeypatch):
    monkeypatch.setenv("FUSANHE_RECOVERY_DIR", str(tmp_path))
    agent = recovery.RecoveryAgent({}, {})
    agent.state["workers"]["mic"] = {"recovering": True, "commandNonce": "previous", "commandAt": 1, "lastBrowserResult": "login_submitted", "blockedSignature": "previous"}
    agent.heartbeat = lambda: None
    agent.observe = lambda worker: {"worker": worker, "reasonCode": "healthy"}
    events = []
    agent.record = lambda *args: events.append(args)
    agent.once()
    assert events == [("mic", "wait", "healthy_verified")]
    assert not set(agent.state["workers"]["mic"]) & {"commandNonce", "commandAt", "lastBrowserResult", "blockedSignature"}


@pytest.mark.parametrize(("reason", "conflict", "expected"), [("healthy", False, False), ("gateway_or_sync_unavailable", False, True), ("healthy", True, True)])
def test_bridge_inflight_batch_is_not_mistaken_for_failed_sync(tmp_path, monkeypatch, reason, conflict, expected):
    from mic_gateway.crm_bridge.state import CrmBridgeState
    monkeypatch.setenv("FUSANHE_RECOVERY_DIR", str(tmp_path / "recovery"))
    monkeypatch.setattr(CrmBridgeState, "pending_batch", lambda self, resource: {"conflict": conflict})
    monkeypatch.setattr(CrmBridgeState, "pending_payload", lambda self, resource: {"fixture": True})
    monkeypatch.setattr(recovery.urllib.request, "urlopen", lambda *a, **kw: io.BytesIO(b'{"session":{"state":"healthy"},"sync":{}}'))
    agent = recovery.RecoveryAgent({}, {"mic": {"agentKey": "fixture", "readApiKey": "fixture"}, "dataRoot": str(tmp_path)})
    agent.request = lambda *a, **kw: {"reasonCode": reason, "sourceAgeSeconds": 10}
    agent.supervisor = lambda *a: MagicMock(stdout="RUNNING")
    result = agent.observe("bridge")
    assert result["pending"] is expected
    assert result["hasReplayPayload"] is expected
    assert result["reasonCode"] == ("pending_batch_conflict" if expected else "healthy")
