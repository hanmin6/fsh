# -*- coding: utf-8 -*-
import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from alibaba_messenger.outbound_worker import OutboundWorker


class DummyBot:
    def __init__(self, logged_in: bool = True):
        self.is_logged_in = logged_in
        self.send_message = AsyncMock()


class DummySettings:
    AGENT_KEY = "test-agent"
    ACCOUNT_HANDLE = "default"


@pytest.mark.asyncio
async def test_heartbeat_reports_online_when_bot_logged_in():
    bot = DummyBot(logged_in=True)
    gateway = MagicMock()
    gateway.heartbeat.return_value = {"ok": True}
    worker = OutboundWorker(bot, gateway, DummySettings())

    result = await worker.send_heartbeat()
    assert result is True
    gateway.heartbeat.assert_called_once_with(status="online", last_error=None)


@pytest.mark.asyncio
async def test_heartbeat_reports_offline_when_bot_not_logged_in():
    bot = DummyBot(logged_in=False)
    gateway = MagicMock()
    gateway.heartbeat.return_value = {"ok": True}
    worker = OutboundWorker(bot, gateway, DummySettings())

    result = await worker.send_heartbeat()
    assert result is True
    gateway.heartbeat.assert_called_once_with(status="offline", last_error="Alibaba messenger session is not logged in")


@pytest.mark.asyncio
async def test_poll_and_execute_once_when_paused():
    bot = DummyBot(logged_in=True)
    gateway = MagicMock()
    gateway.claim.return_value = {"paused": True, "task": None}
    worker = OutboundWorker(bot, gateway, DummySettings())

    executed = await worker.poll_and_execute_once()
    assert executed is False
    gateway.claim.assert_called_once()
    gateway.mark_sending.assert_not_called()


@pytest.mark.asyncio
async def test_poll_and_execute_once_when_no_task():
    bot = DummyBot(logged_in=True)
    gateway = MagicMock()
    gateway.claim.return_value = {"paused": False, "task": None}
    worker = OutboundWorker(bot, gateway, DummySettings())

    executed = await worker.poll_and_execute_once()
    assert executed is False
    gateway.mark_sending.assert_not_called()


@pytest.mark.asyncio
async def test_process_mock_task_succeeds_without_bot_send():
    bot = DummyBot(logged_in=True)
    gateway = MagicMock()
    gateway.mark_sending.return_value = {"ok": True}
    gateway.report_result.return_value = {"ok": True}
    worker = OutboundWorker(bot, gateway, DummySettings())

    task = {
        "id": "task-mock-1",
        "inquiryId": "13907077489",
        "buyerName": "Alpha Buyer",
        "body": "Hello mock",
        "executionMode": "mock",
    }
    success = await worker.process_one_task(task)
    assert success is True
    gateway.mark_sending.assert_called_once_with("task-mock-1")
    bot.send_message.assert_not_called()
    assert gateway.report_result.call_count == 1
    _, kwargs = gateway.report_result.call_args
    assert kwargs["task_id"] == "task-mock-1"
    assert kwargs["success"] is True
    assert "MOCK" in kwargs["platform_message_id"]


@pytest.mark.asyncio
async def test_process_real_task_calls_bot_and_reports_success():
    bot = DummyBot(logged_in=True)
    bot.send_message.return_value = {
        "success": True,
        "message": "Sent",
        "data": {"sent_at": "2026-09-22T12:00:00"}
    }
    gateway = MagicMock()
    gateway.mark_sending.return_value = {"ok": True}
    gateway.report_result.return_value = {"ok": True}
    worker = OutboundWorker(bot, gateway, DummySettings())

    task = {
        "id": "task-real-1",
        "inquiryId": "13907077489",
        "buyerName": "Alpha Buyer",
        "body": "Hello real customer",
        "executionMode": "real",
    }
    success = await worker.process_one_task(task)
    assert success is True
    gateway.mark_sending.assert_called_once_with("task-real-1")
    bot.send_message.assert_called_once_with(
        buyer_name="Alpha Buyer",
        message="Hello real customer",
        inquiry_id="13907077489"
    )
    gateway.report_result.assert_called_once_with(
        task_id="task-real-1",
        success=True,
        platform_message_id="2026-09-22T12:00:00",
        error_message=None
    )


@pytest.mark.asyncio
async def test_process_real_task_handles_bot_failure():
    bot = DummyBot(logged_in=True)
    bot.send_message.return_value = {
        "success": False,
        "message": "Element not found on page",
        "data": {}
    }
    gateway = MagicMock()
    gateway.mark_sending.return_value = {"ok": True}
    gateway.report_result.return_value = {"ok": True}
    worker = OutboundWorker(bot, gateway, DummySettings())

    task = {
        "id": "task-real-2",
        "inquiryId": "13907077489",
        "buyerName": "Alpha Buyer",
        "body": "Hello failure",
        "executionMode": "real",
    }
    success = await worker.process_one_task(task)
    assert success is False
    gateway.report_result.assert_called_once_with(
        task_id="task-real-2",
        success=False,
        platform_message_id=None,
        error_message="Element not found on page"
    )


@pytest.mark.asyncio
async def test_dry_run_mode_bypasses_bot_call():
    bot = DummyBot(logged_in=True)
    gateway = MagicMock()
    gateway.mark_sending.return_value = {"ok": True}
    gateway.report_result.return_value = {"ok": True}
    worker = OutboundWorker(bot, gateway, DummySettings(), dry_run=True)

    task = {
        "id": "task-dry-1",
        "inquiryId": "13907077489",
        "buyerName": "Alpha Buyer",
        "body": "Hello dry run",
        "executionMode": "real",
    }
    success = await worker.process_one_task(task)
    assert success is True
    bot.send_message.assert_not_called()
    assert gateway.report_result.call_count == 1
    _, kwargs = gateway.report_result.call_args
    assert "DRYRUN" in kwargs["platform_message_id"]


def test_run_worker_parser_defaults():
    from alibaba_messenger.run_worker import parser
    args = parser().parse_args([])
    assert args.headless is False
    assert args.dry_run is False
    assert args.once is False
    assert args.interval == 15.0
    assert args.heartbeat_interval == 60.0


def test_run_worker_main_once_dry_run(monkeypatch):
    from unittest.mock import patch
    from alibaba_messenger.run_worker import main

    monkeypatch.setenv("FUSANHE_AGENT_TOKEN", "test-token")
    monkeypatch.setenv("CRM_API_URL", "http://localhost:8080/api/v1")

    with patch("alibaba_messenger.run_worker.CrmGateway") as MockGateway:
        mock_gw_instance = MockGateway.return_value
        mock_gw_instance.heartbeat.return_value = {"ok": True}
        mock_gw_instance.claim.return_value = {"paused": True, "task": None}

        exit_code = main(["--dry-run", "--once"])
        assert exit_code == 0
        mock_gw_instance.heartbeat.assert_called_once_with(status="online", last_error=None)
        mock_gw_instance.claim.assert_called_once()

