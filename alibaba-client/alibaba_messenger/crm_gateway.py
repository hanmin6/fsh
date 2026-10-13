"""Authenticated local CRM gateway with redacted error messages."""
from __future__ import annotations

import requests


class CrmPermanentError(RuntimeError): pass
class CrmTransientError(RuntimeError): pass
class CrmAuthError(RuntimeError): pass


class CrmGateway:
    def __init__(self, base_url: str, agent_key: str, agent_token: str, session: requests.Session | None = None):
        self.base_url, self.agent_key, self.agent_token = base_url.rstrip("/"), agent_key, agent_token
        self.session = session or requests.Session()

    def _decode(self, response, request_id: str) -> dict:
        try:
            data = response.json()
        except ValueError:
            data = None
        if response.status_code in (401, 403):
            raise CrmAuthError(f"CRM authentication failed; requestId={request_id}")
        if response.status_code in (400, 404, 409, 413, 422):
            code = str((data or {}).get("code") or (data or {}).get("error") or response.status_code)
            raise CrmPermanentError(f"CRM rejected request: {code}; requestId={request_id}")
        if response.status_code == 429 or response.status_code >= 500:
            raise CrmTransientError(f"CRM unavailable: {response.status_code}; requestId={request_id}")
        response.raise_for_status()
        if data is None:
            raise CrmTransientError(f"CRM returned non-JSON response; requestId={request_id}")
        return data

    def register(self, bootstrap: str, rotate: bool = True) -> str:
        response = self.session.post(f"{self.base_url}/Fusanhe/agent/register", json={
            "agentKey": self.agent_key, "name": "Guangzhou Alibaba Agent", "mode": "real",
            "capabilities": ["Alibaba"], "rotateCredential": rotate,
        }, headers={"X-Automation-Token": bootstrap}, timeout=(5, 30))
        data = self._decode(response, response.headers.get("X-Request-Id", "register"))
        token = str(data.get("agentToken") or "")
        if not token: raise CrmPermanentError("CRM did not issue an agent token")
        return token

    def _headers(self, request_id: str = "") -> dict:
        headers = {
            "X-Agent-Key": self.agent_key,
            "X-Agent-Token": self.agent_token,
            "X-Automation-Token": self.agent_token,
            "Content-Type": "application/json",
        }
        if request_id:
            headers["X-Request-Id"] = request_id
        return headers

    def sync_batch(self, payload: dict, request_id: str) -> dict:
        try:
            response = self.session.post(
                f"{self.base_url}/Fusanhe/alibaba/sync",
                json=payload,
                headers=self._headers(request_id),
                timeout=(5, 30),
            )
        except requests.Timeout as exc:
            raise CrmTransientError(f"CRM timed out; requestId={request_id}") from exc
        except requests.RequestException as exc:
            raise CrmTransientError(f"CRM request failed; requestId={request_id}") from exc
        return self._decode(response, request_id)

    def heartbeat(self, status: str = "online", last_error: str | None = None, request_id: str = "heartbeat", *, capture_success: dict | None = None) -> dict:
        payload = {"agentKey": self.agent_key, "status": status}
        if last_error is not None:
            payload["lastError"] = last_error
        if capture_success is not None:
            payload["captureSuccess"] = capture_success
        try:
            response = self.session.post(
                f"{self.base_url}/Fusanhe/agent/heartbeat",
                json=payload,
                headers=self._headers(request_id),
                timeout=(5, 15),
            )
        except requests.Timeout as exc:
            raise CrmTransientError(f"CRM timed out; requestId={request_id}") from exc
        except requests.RequestException as exc:
            raise CrmTransientError(f"CRM request failed; requestId={request_id}") from exc
        return self._decode(response, request_id)

    def claim(self, request_id: str = "claim", scheduled_only: bool = False) -> dict:
        try:
            response = self.session.post(
                f"{self.base_url}/Fusanhe/agent/claim",
                json={"agentKey": self.agent_key, **({"scheduledOnly": True} if scheduled_only else {})},
                headers=self._headers(request_id),
                timeout=(5, 15),
            )
        except requests.Timeout as exc:
            raise CrmTransientError(f"CRM timed out; requestId={request_id}") from exc
        except requests.RequestException as exc:
            raise CrmTransientError(f"CRM request failed; requestId={request_id}") from exc
        return self._decode(response, request_id)

    def mark_sending(self, task_id: str, request_id: str = "sending") -> dict:
        try:
            response = self.session.post(
                f"{self.base_url}/Fusanhe/agent/task/{task_id}/sending",
                json={"agentKey": self.agent_key},
                headers=self._headers(request_id),
                timeout=(5, 15),
            )
        except requests.Timeout as exc:
            raise CrmTransientError(f"CRM timed out; requestId={request_id}") from exc
        except requests.RequestException as exc:
            raise CrmTransientError(f"CRM request failed; requestId={request_id}") from exc
        return self._decode(response, request_id)

    def report_result(
        self,
        task_id: str,
        success: bool,
        platform_message_id: str | None = None,
        error_message: str | None = None,
        request_id: str = "result",
    ) -> dict:
        payload: dict = {"agentKey": self.agent_key, "success": success}
        if success and platform_message_id is not None:
            payload["platformMessageId"] = platform_message_id
        if not success and error_message is not None:
            payload["errorMessage"] = error_message
        try:
            response = self.session.post(
                f"{self.base_url}/Fusanhe/agent/task/{task_id}/result",
                json=payload,
                headers=self._headers(request_id),
                timeout=(5, 15),
            )
        except requests.Timeout as exc:
            raise CrmTransientError(f"CRM timed out; requestId={request_id}") from exc
        except requests.RequestException as exc:
            raise CrmTransientError(f"CRM request failed; requestId={request_id}") from exc
        return self._decode(response, request_id)
