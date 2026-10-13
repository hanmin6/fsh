from unittest.mock import MagicMock

import pytest
import requests

from alibaba_messenger.crm_gateway import CrmAuthError, CrmGateway, CrmPermanentError, CrmTransientError


def response(status, data):
    result = MagicMock(status_code=status)
    result.json.return_value = data
    result.headers = {"X-Request-Id": "crm-request"}
    return result


def test_sync_batch_uses_agent_headers_and_safe_timeout():
    session = MagicMock()
    session.post.return_value = response(200, {"ok": True})
    gateway = CrmGateway("http://127.0.0.1:8080/api/v1", "agent", "agent-token", session=session)
    assert gateway.sync_batch({"messages": []}, "request-1") == {"ok": True}
    _, kwargs = session.post.call_args
    assert kwargs["headers"]["X-Agent-Key"] == "agent"
    assert kwargs["headers"]["X-Request-Id"] == "request-1"
    assert kwargs["timeout"] == (5, 30)
    assert kwargs.get("verify", True) is not False


@pytest.mark.parametrize("status,error", [(400, CrmPermanentError), (401, CrmAuthError), (429, CrmTransientError), (500, CrmTransientError)])
def test_gateway_classifies_errors_without_echoing_body_or_headers(status, error):
    session = MagicMock()
    session.post.return_value = response(status, {"error": "safe-code", "body": "customer body"})
    gateway = CrmGateway("http://127.0.0.1:8080/api/v1", "agent", "secret", session=session)
    with pytest.raises(error) as caught:
        gateway.sync_batch({"messages": [{"body": "customer body"}]}, "request-1")
    assert "customer body" not in str(caught.value)
    assert "secret" not in str(caught.value)


def test_registration_returns_one_time_token_without_storing_it():
    session = MagicMock()
    session.post.return_value = response(200, {"agentToken": "one-time-token"})
    gateway = CrmGateway("http://127.0.0.1:8080/api/v1", "agent", "", session=session)
    assert gateway.register("bootstrap", rotate=True) == "one-time-token"
    assert gateway.agent_token == ""


def test_non_json_400_is_permanent_not_transient():
    session = MagicMock()
    bad = response(400, {})
    bad.json.side_effect = ValueError("not json")
    session.post.return_value = bad
    gateway = CrmGateway("http://127.0.0.1:8080/api/v1", "agent", "secret", session=session)

    with pytest.raises(CrmPermanentError) as caught:
        gateway.sync_batch({"messages": []}, "request-400")

    assert "400" in str(caught.value)
    assert "secret" not in str(caught.value)


def test_heartbeat_sends_agent_status_and_headers():
    session = MagicMock()
    session.post.return_value = response(200, {"ok": True})
    gateway = CrmGateway("http://127.0.0.1:8080/api/v1", "test-agent", "agent-token", session=session)
    res = gateway.heartbeat(status="online", last_error=None)
    assert res == {"ok": True}
    url, kwargs = session.post.call_args
    assert url[0] == "http://127.0.0.1:8080/api/v1/Fusanhe/agent/heartbeat"
    assert kwargs["json"]["agentKey"] == "test-agent"
    assert kwargs["json"]["status"] == "online"
    assert kwargs["headers"]["X-Agent-Key"] == "test-agent"
    assert kwargs["headers"]["X-Agent-Token"] == "agent-token"
    assert kwargs["headers"]["X-Automation-Token"] == "agent-token"


def test_successful_capture_is_explicit_and_optional():
    session = MagicMock()
    session.post.return_value = response(200, {"ok": True})
    gateway = CrmGateway("http://127.0.0.1:8080/api/v1", "agent", "agent-token", session=session)
    gateway.heartbeat()
    assert "captureSuccess" not in session.post.call_args.kwargs["json"]
    capture = {"channelType": "Alibaba", "accountHandle": "main"}
    gateway.heartbeat(capture_success=capture)
    assert session.post.call_args.kwargs["json"]["captureSuccess"] == capture


def test_claim_sends_agent_key_and_returns_payload():
    session = MagicMock()
    session.post.return_value = response(200, {"paused": False, "task": {"id": "task-1", "body": "hello"}})
    gateway = CrmGateway("http://127.0.0.1:8080/api/v1", "test-agent", "agent-token", session=session)
    res = gateway.claim()
    assert res["paused"] is False
    assert res["task"]["id"] == "task-1"
    url, kwargs = session.post.call_args
    assert url[0] == "http://127.0.0.1:8080/api/v1/Fusanhe/agent/claim"
    assert kwargs["json"] == {"agentKey": "test-agent"}


def test_mark_sending_posts_to_task_sending_endpoint():
    session = MagicMock()
    session.post.return_value = response(200, {"ok": True})
    gateway = CrmGateway("http://127.0.0.1:8080/api/v1", "test-agent", "agent-token", session=session)
    res = gateway.mark_sending("task-123")
    assert res == {"ok": True}
    url, kwargs = session.post.call_args
    assert url[0] == "http://127.0.0.1:8080/api/v1/Fusanhe/agent/task/task-123/sending"
    assert kwargs["json"] == {"agentKey": "test-agent"}


def test_report_result_handles_success_and_failure():
    session = MagicMock()
    session.post.return_value = response(200, {"ok": True})
    gateway = CrmGateway("http://127.0.0.1:8080/api/v1", "test-agent", "agent-token", session=session)
    
    # Success
    res_success = gateway.report_result("task-123", success=True, platform_message_id="msg-999")
    assert res_success == {"ok": True}
    url, kwargs = session.post.call_args
    assert url[0] == "http://127.0.0.1:8080/api/v1/Fusanhe/agent/task/task-123/result"
    assert kwargs["json"]["success"] is True
    assert kwargs["json"]["platformMessageId"] == "msg-999"

    # Failure
    res_fail = gateway.report_result("task-123", success=False, error_message="timeout occurred")
    assert res_fail == {"ok": True}
    _, kwargs = session.post.call_args
    assert kwargs["json"]["success"] is False
    assert kwargs["json"]["errorMessage"] == "timeout occurred"
