from __future__ import annotations

import hashlib
import json
import re
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass
from typing import Any, Protocol

from mic_gateway.crm_bridge.config import CrmBridgeConfig
from mic_gateway.crm_bridge.crm_client import CrmClient
from mic_gateway.crm_bridge.state import CrmBridgeState

MAX_CONVERSATION_PAGES = 100


class GatewayClientError(RuntimeError):
    """Gateway request failed or returned an invalid response."""


class GatewayClient(Protocol):
    def status(self) -> dict[str, Any]: ...

    def list_conversations(
        self, limit: int = 200, cursor: str | None = None
    ) -> dict[str, Any]: ...

    def submit_message(self, conversation_id: str, payload: dict[str, Any]) -> dict[str, Any]: ...

    def get_job(self, job_id: str) -> dict[str, Any]: ...


@dataclass(frozen=True, slots=True)
class OutboundJob:
    task_id: str
    source_id: str
    idempotency_key: str
    gateway_job_id: str | None


@dataclass(frozen=True, slots=True)
class WorkerResult:
    status: str
    task_id: str | None = None
    job_id: str | None = None
    action_required: bool = False


class MicGatewayClient:
    """Authenticated synchronous client for the MIC CRM read and agent-send APIs."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        *,
        opener: Any | None = None,
        timeout: float = 10.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.opener = opener or urllib.request.build_opener(_NoRedirectHandler()).open
        self.timeout = timeout

    def status(self) -> dict[str, Any]:
        return self._request("GET", "/v1/status")

    def list_conversations(
        self, limit: int = 200, cursor: str | None = None
    ) -> dict[str, Any]:
        parameters = {"limit": limit, "cursor": cursor} if cursor else {"limit": limit}
        query = urllib.parse.urlencode(parameters)
        return self._request("GET", f"/v1/conversations?{query}")

    def submit_message(self, conversation_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/v1/conversations/{urllib.parse.quote(conversation_id, safe='')}/messages",
            payload,
        )

    def get_job(self, job_id: str) -> dict[str, Any]:
        return self._request("GET", f"/v1/jobs/{urllib.parse.quote(job_id, safe='')}")

    def _request(
        self, method: str, path: str, payload: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        body = None if payload is None else json.dumps(payload, separators=(",", ":")).encode()
        request = urllib.request.Request(
            self.base_url + path,
            data=body,
            headers={"X-API-Key": self.api_key, "Content-Type": "application/json"},
            method=method,
        )
        try:
            response = self.opener(request, timeout=self.timeout)
            raw = response.read()
        except urllib.error.HTTPError as exc:
            raise GatewayClientError(f"MIC gateway returned HTTP {exc.code}") from None
        except (TimeoutError, OSError, urllib.error.URLError):
            raise GatewayClientError("MIC gateway transport failed") from None
        try:
            value = json.loads(raw)
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise GatewayClientError("MIC gateway returned invalid JSON") from None
        if not isinstance(value, dict):
            raise GatewayClientError("MIC gateway returned an invalid response")
        return value


class MicOutboundWorker:
    """Reconcile individually approved CRM tasks through the MIC gateway Outbox."""

    def __init__(
        self,
        *,
        crm: CrmClient,
        gateway: GatewayClient,
        state: CrmBridgeState,
        poll_interval_seconds: float = 1.0,
    ) -> None:
        self.crm = crm
        self.gateway = gateway
        self.state = state
        self.poll_interval_seconds = max(0.0, poll_interval_seconds)

    @classmethod
    def from_config(
        cls,
        *,
        config: CrmBridgeConfig,
        crm: CrmClient,
        state: CrmBridgeState,
        poll_interval_seconds: float = 1.0,
    ) -> MicOutboundWorker:
        """Build a send worker after the operator registers its CRM Agent.

        Startup precondition: run the bridge's explicit register command, then
        provide the issued credential through ``MIC_CRM_AGENT_TOKEN``. This
        worker never registers or rotates credentials automatically.
        """
        send_key = config.mic_send_api_key
        if not send_key:
            raise ValueError("MIC gateway send API key is required")
        if not config.crm_agent_token:
            raise ValueError(
                "CRM Agent token is required; register the Agent and set MIC_CRM_AGENT_TOKEN"
            )
        config.validate()
        return cls(
            crm=crm,
            gateway=MicGatewayClient(config.mic_base_url, send_key),
            state=state,
            poll_interval_seconds=poll_interval_seconds,
        )

    @staticmethod
    def idempotency_key(task_id: str) -> str:
        # Keep task ID-derived stable key within the gateway's 128-character limit.
        digest = hashlib.sha256(task_id.encode("utf-8")).hexdigest()
        return f"crm-task-{digest}"

    def run_once(self) -> WorkerResult:
        try:
            gateway_status = self.gateway.status()
        except Exception:
            if not self._heartbeat("offline", "mic_gateway_unavailable"):
                return WorkerResult("heartbeat_failed", action_required=True)
            return WorkerResult("gateway_unavailable", action_required=True)

        heartbeat_status, status_error = _gateway_heartbeat_status(
            gateway_status.get("state")
        )
        if not self._heartbeat(heartbeat_status, status_error):
            return WorkerResult("heartbeat_failed", action_required=True)
        if not _gateway_send_ready(gateway_status):
            return WorkerResult("gateway_not_ready", action_required=True)

        pending = [
            OutboundJob(
                task_id=str(entry["task_id"]),
                source_id=str(entry["source_id"]),
                idempotency_key=str(entry["idempotency_key"]),
                gateway_job_id=entry["gateway_job_id"],
            )
            for entry in self.state.outbound_jobs()
        ]
        if pending:
            return self._reconcile(pending[0])

        claim = self.crm.claim(request_id=_request_id())
        if not isinstance(claim.get("paused"), bool):
            return WorkerResult("blocked", action_required=True)
        if claim["paused"]:
            return WorkerResult("paused")
        task = claim.get("task")
        if task is None:
            return WorkerResult("idle")
        if not isinstance(task, dict) or not _valid_task(task):
            task_id = _task_id(task)
            if not self._heartbeat(heartbeat_status, "claimed_task_invalid"):
                return WorkerResult("heartbeat_failed", task_id, action_required=True)
            return WorkerResult("rejected", task_id, action_required=True)

        task_id = str(task["id"])
        source_id = str(task["inquiryId"])
        body = str(task["body"])
        key = self.idempotency_key(task_id)
        try:
            conversation_id = self._resolve_conversation(source_id)
        except Exception:
            if not self._heartbeat(heartbeat_status, "source_conversation_unavailable"):
                return WorkerResult("heartbeat_failed", task_id, action_required=True)
            return WorkerResult("source_unavailable", task_id, action_required=True)

        self.state.prepare_outbound_job(task_id, source_id, key)
        # CRM's sending transition is the final pre-submit check for global pause
        # and human takeover.
        try:
            self.crm.mark_sending(task_id, request_id=_request_id())
        except Exception:
            self.state.remove_outbound_job(task_id)
            return WorkerResult("blocked", task_id, action_required=True)

        try:
            job = self.gateway.submit_message(
                conversation_id,
                {
                    "idempotency_key": key,
                    "intent": "greeting",
                    "content": body,
                    "caller_reference": task_id,
                },
            )
        except Exception:
            # Keep the task/key journal for manual outbox reconciliation. The
            # message body is not persisted, so this worker will not resubmit.
            return WorkerResult("pending", task_id, action_required=True)
        job_id = str(job.get("id") or "").strip()
        if not job_id:
            return WorkerResult("pending", task_id, action_required=True)
        self.state.set_outbound_gateway_job(task_id, job_id)
        return self._reconcile(OutboundJob(task_id, source_id, key, job_id))

    def _reconcile(self, job: OutboundJob) -> WorkerResult:
        if job.gateway_job_id is None:
            # The approved text is intentionally not persisted. If the submit
            # response was lost before its job ID was journaled, fail closed for
            # operator reconciliation instead of reconstructing or resending it.
            return WorkerResult("pending", job.task_id, action_required=True)

        try:
            status = self.gateway.get_job(job.gateway_job_id or "")
        except Exception:
            return WorkerResult("pending", job.task_id, job.gateway_job_id, True)

        state = str(status.get("state", "")).strip().lower()
        if state in {"queued", "sending", "uncertain", "requires_human_review"}:
            self.state.update_outbound_status(job.task_id, state)
        if state == "sent":
            metadata = status.get("safe_result_metadata")
            message_id = metadata.get("source_message_id") if isinstance(metadata, dict) else None
            message_id = str(message_id or "").strip()
            if not message_id:
                return WorkerResult("pending", job.task_id, job.gateway_job_id, True)
            self.crm.report_result(
                job.task_id,
                True,
                platform_message_id=message_id,
                request_id=_request_id(),
            )
            self.state.remove_outbound_job(job.task_id)
            return WorkerResult("sent", job.task_id, job.gateway_job_id)
        if state == "failed":
            code = _safe_failure_code(status.get("failure_code"))
            self.crm.report_result(
                job.task_id,
                False,
                error_message=f"mic_gateway_{code}",
                request_id=_request_id(),
            )
            self.state.remove_outbound_job(job.task_id)
            return WorkerResult("failed", job.task_id, job.gateway_job_id)

        return WorkerResult("pending", job.task_id, job.gateway_job_id, True)

    def _resolve_conversation(self, source_id: str) -> str:
        cursor: str | None = None
        seen_cursors: set[str | None] = set()
        matches: list[str] = []
        for _ in range(MAX_CONVERSATION_PAGES):
            if cursor in seen_cursors:
                raise GatewayClientError("MIC conversation pagination repeated a cursor")
            seen_cursors.add(cursor)
            page = self.gateway.list_conversations(limit=200, cursor=cursor)
            items = page.get("items")
            if not isinstance(items, list):
                raise GatewayClientError("MIC gateway returned invalid conversations")
            for conversation in items:
                if isinstance(conversation, dict) and conversation.get("source_id") == source_id:
                    gateway_id = str(conversation.get("id") or "").strip()
                    if gateway_id:
                        matches.append(gateway_id)
            cursor_value = page.get("next_cursor")
            if cursor_value is None or cursor_value == "":
                break
            if not isinstance(cursor_value, str):
                raise GatewayClientError("MIC gateway returned an invalid conversation cursor")
            cursor = cursor_value
        else:
            raise GatewayClientError("MIC conversation pagination exceeded its page limit")
        if len(matches) != 1:
            raise GatewayClientError("MIC source conversation did not resolve uniquely")
        return matches[0]

    def _heartbeat(self, status: str, last_error: str | None = None) -> bool:
        try:
            self.crm.heartbeat(
                status=status,
                last_error=last_error,
                request_id=_request_id(),
            )
        except Exception:
            return False
        return True


def _valid_task(task: dict[str, Any]) -> bool:
    return (
        bool(str(task.get("id") or "").strip())
        and task.get("channelType") == "MadeInChina"
        and task.get("executionMode") == "real"
        and bool(str(task.get("inquiryId") or "").strip())
        and bool(str(task.get("body") or "").strip())
    )


def _gateway_send_ready(status: dict[str, Any]) -> bool:
    overall = status.get("state")
    if not isinstance(overall, str) or overall not in {"healthy", "degraded"}:
        return False

    session = status.get("session")
    if not isinstance(session, dict) or session.get("state") != "healthy":
        return False

    sync = status.get("sync")
    conversations = sync.get("conversations") if isinstance(sync, dict) else None
    if not isinstance(conversations, dict):
        return False
    if conversations.get("fresh") is not True:
        return False
    failure_count = conversations.get("failure_count")
    if type(failure_count) is not int or failure_count != 0:
        return False
    if conversations.get("last_error_code") or conversations.get("paused_reason"):
        return False

    outbox = status.get("outbox")
    if not isinstance(outbox, dict):
        return False
    uncertain = outbox.get("uncertain")
    return type(uncertain) is int and uncertain == 0


def _gateway_heartbeat_status(state: Any) -> tuple[str, str | None]:
    if not isinstance(state, str):
        return "degraded", "mic_gateway_status_invalid"
    normalized = state.strip().lower()
    if normalized == "healthy":
        return "online", None
    if normalized in {
        "degraded",
        "starting",
        "operator_action_required",
        "site_contract_error",
        "stopped",
    }:
        return normalized, None
    return "degraded", "mic_gateway_status_invalid"


def _task_id(task: Any) -> str | None:
    return str(task.get("id")) if isinstance(task, dict) and task.get("id") else None


def _safe_failure_code(value: Any) -> str:
    code = str(value or "unknown").strip().lower()
    if len(code) > 64 or re.fullmatch(r"[a-z0-9_-]+", code) is None:
        return "unknown"
    return code


def _request_id() -> str:
    return f"mic-worker-{uuid.uuid4().hex}"


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(
        self, req: Any, fp: Any, code: int, msg: str, headers: Any, newurl: str
    ) -> None:
        return None
