"""Resident, account-scoped recovery agent; the CRM relay supplies GPT-6.1 Sol."""
from __future__ import annotations

import argparse
import fcntl
import json
import os
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path

from gateway_recovery_login import directory, write_json

MODEL = "gpt-6.1-sol"
WORKERS = {"mic", "bridge", "alibaba"}


def age(value: str | None) -> int:
    try:
        return max(0, min(31536000, int(time.time() - datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp())))
    except (ValueError, TypeError, AttributeError):
        return 31536000


def source_health(status: dict, crm_age: int) -> tuple[int, bool, bool]:
    """Use actual source progress, not only the bridge's CRM receipt time."""
    checkpoints = status.get("sync", {})
    source = checkpoints.get("conversations", {})
    source_age = max(crm_age, age(source.get("last_success_at"))) if source else crm_age
    poller = status.get("poller")
    if isinstance(poller, dict):
        workers = poller.get("workers", [])
        expected = {"mic-health", "mic-conversations", "mic-orders", "mic-outbox"}
        live = {w.get("name") for w in workers if not w.get("done")}
        progress = [v.get("last_success_at") for k, v in checkpoints.items()
                    if k == "conversations" or k.startswith("messages:")]
        progress_age = min((age(v) for v in progress if v), default=31536000)
        unresponsive = not expected.issubset(live) or (poller.get("locked") is True and progress_age > 900)
        busy = not unresponsive and any("sync_conversations_and_messages" in w.get("steps", []) for w in workers)
    else:
        unresponsive = False
        busy = any(not v.get("failure_count") and v.get("last_attempt_at")
                   and v["last_attempt_at"] > (v.get("last_success_at") or "")
                   and age(v["last_attempt_at"]) < 900 for v in checkpoints.values())
    return source_age, busy, unresponsive


class RecoveryAgent:
    def __init__(self, config: dict, channels: dict):
        self.config, self.channels = config, channels
        self.path = directory() / "agent-state.json"
        try:
            self.state = json.loads(self.path.read_text())
        except (OSError, ValueError):
            self.state = {"workers": {}, "history": []}

    def request(self, worker: str, operation: str, **body) -> dict:
        channel = "Alibaba" if worker == "alibaba" else "MadeInChina"
        c = self.channels["alibaba" if channel == "Alibaba" else "mic"]
        payload = {"operation": operation, "channelType": channel, "accountHandle": c["accountHandle"], **body}
        headers = {"Content-Type": "application/json", "X-Agent-Key": self.config["agentKey"], "X-Agent-Token": self.config["agentToken"], "X-Request-Id": "recovery-" + uuid.uuid4().hex}
        req = urllib.request.Request(self.channels["crmUrl"].rstrip("/") + "/api/v1/Fusanhe/agent/recovery", json.dumps(payload).encode(), headers)
        with urllib.request.urlopen(req, timeout=65) as response:
            return json.load(response)

    def heartbeat(self):
        req = urllib.request.Request(self.channels["crmUrl"] + "/api/v1/Fusanhe/agent/heartbeat", json.dumps({"agentKey": self.config["agentKey"], "status": "online"}).encode(), {"Content-Type": "application/json", "X-Agent-Key": self.config["agentKey"], "X-Agent-Token": self.config["agentToken"]})
        with urllib.request.urlopen(req, timeout=15) as response:
            response.read()

    @staticmethod
    def supervisor(action: str, worker: str) -> subprocess.CompletedProcess:
        if action not in {"status", "start", "stop"} or worker not in WORKERS:
            raise ValueError("unsupported supervisor operation")
        return subprocess.run(["supervisorctl", action, worker], capture_output=True, text=True, timeout=35)

    def observe(self, worker: str) -> dict:
        c = self.channels["alibaba" if worker == "alibaba" else "mic"]
        remote = self.request(worker, "observe", collectorKey=c["agentKey"])
        running = "RUNNING" in self.supervisor("status", worker).stdout
        session, busy, unresponsive = "healthy", False, False
        if worker in {"mic", "bridge"}:
            try:
                req = urllib.request.Request("http://127.0.0.1:8787/v1/status", headers={"X-API-Key": c["readApiKey"]})
                with urllib.request.urlopen(req, timeout=10) as response:
                    status = json.load(response)
                session = {"healthy": "healthy", "authentication_required": "login_required", "verification_required": "verification_required"}.get(status.get("session", {}).get("state"), "unavailable")
                source_age, busy, unresponsive = source_health(status, remote["sourceAgeSeconds"])
                if worker == "mic":
                    remote["sourceAgeSeconds"] = source_age
            except Exception:
                session = "unavailable"
        else:
            try:
                status = json.loads((Path(self.channels["dataRoot"]) / "alibaba/browser-status.json").read_text())
                session = {"ready": "healthy", "login_required": "login_required", "verification_required": "verification_required"}.get(status["state"], "unavailable")
            except (OSError, ValueError, KeyError):
                session = "unavailable"
        pending, replay = False, False
        if worker == "bridge":
            from mic_gateway.crm_bridge.state import CrmBridgeState
            journal = CrmBridgeState(Path(self.channels["dataRoot"]) / "mic")
            rows = [journal.pending_batch(r) for r in ("conversations", "conversations:once")]
            # Normal imports briefly stage a pending request while it is in
            # flight. Only failed, conflicted, stopped or stale imports need
            # intervention; never interrupt a healthy batch in transit.
            pending = any(rows) and (any(row and row.get("conflict") for row in rows)
                or not running or remote["sourceAgeSeconds"] > 1800
                or remote["reasonCode"] in {"pending_batch_conflict", "gateway_or_sync_unavailable", "sync_failed"})
            replay = pending and any(journal.pending_payload(r) is not None for r in ("conversations", "conversations:once"))
        reason = "process_stopped" if not running else "pending_batch_conflict" if pending else session if session in {"login_required", "verification_required"} else "worker_unresponsive" if unresponsive and worker == "mic" else "browser_unavailable" if session == "unavailable" else "source_stale" if remote["sourceAgeSeconds"] > 1800 else remote["reasonCode"]
        if reason == "source_sync_pending_or_failed":
            reason = "source_stale"
        return {"worker": worker, "processRunning": running, "sessionState": session,
                "sourceAgeSeconds": remote["sourceAgeSeconds"], "sourceBusy": busy,
                "pending": pending, "hasReplayPayload": replay,
                "autoLoginSupported": worker != "bridge" and self.config.get("savedLoginEnabled", True), "reasonCode": reason}

    def record(self, worker: str, action: str, code: str):
        event = {"at": time.time(), "worker": worker, "action": action, "resultCode": code, "model": MODEL}
        self.state["history"] = (self.state.get("history", []) + [event])[-100:]
        self.state["updatedAt"] = time.time()
        write_json(self.path, self.state)
        print(json.dumps(event), flush=True)
        try:
            self.request(worker, "report", action=action, resultCode=code)
        except Exception:
            pass

    def replay(self) -> str:
        from mic_gateway.crm_bridge.crm_client import CrmClient
        from mic_gateway.crm_bridge.state import CrmBridgeState
        c = self.channels["mic"]
        self.supervisor("stop", "bridge")
        try:
            journal = CrmBridgeState(Path(self.channels["dataRoot"]) / "mic")
            backups = directory() / "backups"
            backups.mkdir(mode=0o700, exist_ok=True)
            backup = backups / ("journal-" + str(int(time.time())) + ".sqlite3")
            with sqlite3.connect(journal.path) as src, sqlite3.connect(backup) as dst:
                src.backup(dst)
            backup.chmod(0o600)
            crm = CrmClient(self.channels["crmUrl"] + "/api/v1", c["agentKey"], c["agentToken"])
            for resource in ("conversations", "conversations:once"):
                pending = journal.pending_batch(resource)
                if not pending:
                    continue
                checked = self.request("bridge", "verify_batch", batchRequestId=pending["request_id"], payloadHash=pending["payload_sha256"])
                if checked.get("state") == "accepted":
                    journal.mark_pending_conflict(resource, str(pending["request_id"]))
                    journal.resolve_pending_by_operator(resource, str(pending["request_id"]), accepted=True)
                    continue
                if checked.get("state") == "mismatch":
                    return "batch_hash_mismatch_needs_human"
                payload = journal.pending_payload(resource)
                if payload is None:
                    return "missing_original_batch_needs_human"
                verified = crm.sync_batch(payload, str(pending["request_id"]))
                journal.confirm_batch(resource, str(pending["request_id"]), verified)
            return "batch_replay_confirmed"
        except Exception:
            return "batch_replay_unconfirmed_needs_human"
        finally:
            self.supervisor("start", "bridge")

    def act(self, worker: str, action: str) -> str:
        if action == "restart_worker":
            self.supervisor("stop", worker)
            return "worker_started" if self.supervisor("start", worker).returncode == 0 else "worker_start_failed"
        if action in {"auto_login", "retry_sync"}:
            if worker == "bridge":
                return "unsupported_browser_worker"
            nonce = uuid.uuid4().hex
            write_json(directory() / (worker + ".command.json"), {"worker": worker, "action": action, "nonce": nonce, "expiresAt": time.time() + 300})
            self.state["workers"][worker]["commandNonce"] = nonce
            self.state["workers"][worker]["commandAt"] = time.time()
            return "browser_recovery_queued"
        if action == "replay_pending" and worker == "bridge":
            return self.replay()
        return "human_action_required" if action == "needs_human" else "observing"

    def once(self, smoke: bool = False):
        self.heartbeat()
        for worker in ("mic", "bridge", "alibaba"):
            o = self.observe(worker)
            slot = self.state["workers"].setdefault(worker, {})
            slot["observation"] = o
            if o["reasonCode"] == "healthy":
                if slot.pop("recovering", False):
                    self.record(worker, "wait", "healthy_verified")
                slot["failures"] = 0
                slot.pop("blockedSignature", None)
                # A later login expiration must not inherit the previous
                # command's timeout or submitted-login result.
                for key in ("commandNonce", "commandAt", "lastBrowserResult"):
                    slot.pop(key, None)
                if not smoke:
                    continue
            else:
                slot["failures"] = slot.get("failures", 0) + 1
            # Do not ask the model repeatedly about the same unresolved condition.
            signature = json.dumps({k: o[k] for k in ("processRunning", "sessionState", "pending", "hasReplayPayload", "reasonCode")}, sort_keys=True)
            now = time.time()
            nonce = slot.get("commandNonce")
            if nonce:
                try:
                    outcome = json.loads((directory() / (worker + ".result.json")).read_text())
                except (OSError, ValueError):
                    outcome = {}
                if outcome.get("nonce") == nonce:
                    code = outcome.get("code", "login_browser_operation_failed")
                    if code not in {"login_submitted", "retry_sync_requested"}:
                        slot["blockedSignature"] = signature
                        self.record(worker, "needs_human", "browser_recovery_needs_human")
                    slot.pop("commandNonce", None)
                    slot["lastBrowserResult"] = code
                elif now - slot.get("commandAt", now) > 300:
                    slot.pop("commandNonce", None)
                    recent = [x for x in slot.get("attempts", []) if now - x < 3600]
                    if worker != "bridge" and o["sessionState"] == "healthy" and not o["sourceBusy"] and not o["pending"] and len(recent) < 4:
                        # A healthy login with an idle, non-consuming poller is
                        # recoverable; do not permanently silence this condition.
                        code = self.act(worker, "restart_worker")
                        slot["lastActionAt"] = now
                        slot["attempts"] = recent + [now]
                        slot["recovering"] = True
                        self.record(worker, "restart_worker", code)
                        continue
                    slot["blockedSignature"] = signature
                    self.record(worker, "needs_human", "browser_command_not_consumed")
            if slot.get("lastBrowserResult") == "login_submitted" and o["sessionState"] == "login_required" and now - slot.get("commandAt", now) > 180:
                if slot.get("blockedSignature") != signature:
                    self.record(worker, "needs_human", "login_not_confirmed")
                slot["blockedSignature"] = signature
            attempts = [x for x in slot.get("attempts", []) if now - x < 3600]
            if not smoke and (slot["failures"] < 2 or now - slot.get("lastActionAt", 0) < 300 or len(attempts) >= 4 or slot.get("blockedSignature") == signature):
                continue
            if worker == "bridge" and o["sessionState"] != "healthy" and not o["pending"]:
                continue  # Its browser is managed by the MIC worker.
            plan = self.request(worker, "plan", observation=o)
            if plan.get("model") != MODEL:
                raise RuntimeError("recovery_model_mismatch")
            action = plan["action"]
            slot["lastPlan"] = {"action": action, "reasonZh": plan.get("reasonZh"), "model": MODEL}
            if action not in {"wait", "needs_human"}:
                # Re-read just before acting; stale plans never override a recovery.
                current = self.observe(worker)
                if current["reasonCode"] == "healthy" or (current["sourceBusy"] and action in {"restart_worker", "retry_sync"} and worker != "bridge"):
                    action = "wait"
                elif {k: current[k] for k in ("processRunning", "sessionState", "pending", "hasReplayPayload", "reasonCode")} != {k: o[k] for k in ("processRunning", "sessionState", "pending", "hasReplayPayload", "reasonCode")}:
                    action = "wait"
            code = self.act(worker, action)
            if action != "wait":
                slot["lastActionAt"] = now
            if action not in {"wait", "needs_human"}:
                slot["attempts"] = attempts + [now]
                slot["recovering"] = True
            if action == "needs_human" or code.endswith("needs_human"):
                slot["blockedSignature"] = signature
            self.record(worker, action, code)
        self.state["updatedAt"] = time.time()
        write_json(self.path, self.state)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()
    private = json.loads(args.config.read_text())
    import run_windows_gateway as entry
    channels = entry.configure(Path(private["channelsConfig"]))
    lock = (directory() / "agent.lock").open("a")
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    agent = RecoveryAgent(private, channels)
    while True:
        try:
            agent.once(args.smoke)
        except Exception as error:
            print(json.dumps({"event": "recovery_check_failed", "code": type(error).__name__}), flush=True)
        if args.once:
            break
        time.sleep(60)


if __name__ == "__main__":
    main()
