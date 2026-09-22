# -*- coding: utf-8 -*-
"""
Agent 自动化验收测试套件 (Test Suite for External Testing Agent)
对应文档：alibaba_messenger/TEST_VERIFICATION_SPEC.md
可直接运行：python -m pytest tests/test_agent_suite.py -v
"""

import os
import sys
import tempfile
import asyncio
import subprocess
import pytest
from fastapi.testclient import TestClient

from alibaba_messenger.config import settings, Settings
from alibaba_messenger.dedup import Deduplicator
from alibaba_messenger.alibaba_bot import AlibabaMessengerBot, SendResultStatus
from alibaba_messenger.server import app, browser_lock

client = TestClient(app)

def test_tc_config_001():
    """TC-CONFIG-001: 基础配置与目录创建测试"""
    assert os.path.isabs(settings.BASE_DIR)
    assert os.path.isabs(settings.PROFILE_DIR)
    assert os.path.isabs(settings.LOGS_DIR)
    assert os.path.isabs(settings.SCREENSHOTS_DIR)
    assert os.path.exists(settings.PROFILE_DIR)
    assert os.path.exists(settings.SCREENSHOTS_DIR)
    assert settings.SERVER_PORT == 8000
    assert settings.TYPING_DELAY_MIN_MS == 20
    assert settings.TYPING_DELAY_MAX_MS == 80

def test_tc_dedup_001():
    """TC-DEDUP-001: 防重发校验器生命周期测试"""
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp_path = tmp.name
    try:
        dedup = Deduplicator(storage_file=tmp_path)
        buyer = "Global Trader Co"
        msg = "Season greetings!"

        # 首次不重复
        assert dedup.is_duplicate(buyer, msg) is False
        
        # 记录后应判定为重复
        dedup.record_sent(buyer, msg)
        assert dedup.is_duplicate(buyer, msg) is True
        
        # 消息变化或买家变化不重复
        assert dedup.is_duplicate(buyer, "Different content") is False
        assert dedup.is_duplicate("Other Buyer", msg) is False
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

def test_tc_auth_001():
    """TC-AUTH-001: 未登录保护性拦截测试"""
    response = client.post("/api/message/send", json={
        "buyer_name": "TestBuyer",
        "message": "Hello World"
    })
    assert response.status_code == 401
    payload = response.json()
    assert payload["code"] == 401
    assert payload["success"] is False
    assert payload["status"] == "NEED_LOGIN"

def test_tc_api_status_001():
    """TC-API-STATUS-001: 状态探活接口契约规范测试"""
    response = client.get("/api/status")
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 200
    assert data["success"] is True
    assert "status" in data
    assert "data" in data
    assert "is_logged_in" in data["data"]
    assert "is_busy" in data["data"]
    assert "waiting_queue_count" in data["data"]

def test_tc_api_validation_001():
    """TC-API-VALIDATION-001: 请求参数 Schema 校验测试"""
    # 缺少 message
    r1 = client.post("/api/message/send", json={"buyer_name": "Alice"})
    assert r1.status_code == 422
    
    # 缺少 buyer_name
    r2 = client.post("/api/message/send", json={"message": "Greeting"})
    assert r2.status_code == 422

@pytest.mark.asyncio
async def test_tc_concurrency_lock_001():
    """TC-CONCURRENCY-LOCK-001: 并发排队互斥锁测试"""
    assert not browser_lock.locked()
    async with browser_lock:
        assert browser_lock.locked()
    assert not browser_lock.locked()

def test_tc_cli_001():
    """TC-CLI-001: CLI 启动脚本参数解析测试"""
    res = subprocess.run(
        [sys.executable, "-m", "alibaba_messenger.run_server", "--help"],
        capture_output=True,
        text=True,
        errors="replace"
    )
    assert res.returncode == 0
    assert "usage" in res.stdout.lower()
    assert "--headless" in res.stdout
    assert "--port" in res.stdout
    assert "--host" in res.stdout

def test_tc_recovery_screenshot_001():
    """TC-RECOVERY-SCREENSHOT-001: 异常截屏存储权限与目录验证"""
    test_file = os.path.join(settings.SCREENSHOTS_DIR, "agent_verify_test.png")
    with open(test_file, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\nFakeScreenshotData")
    assert os.path.exists(test_file)
    os.remove(test_file)
    assert not os.path.exists(test_file)

def test_tc_bot_contracts_001():
    """TC-BOT-CONTRACTS-001: 机器人枚举状态与接口规范测试"""
    assert SendResultStatus.SENT == "SENT"
    assert SendResultStatus.BUYER_NOT_FOUND == "BUYER_NOT_FOUND"
    assert SendResultStatus.DUPLICATE_IGNORED == "DUPLICATE_IGNORED"
    assert SendResultStatus.NEED_LOGIN == "NEED_LOGIN"
    assert SendResultStatus.QUEUE_TIMEOUT == "QUEUE_TIMEOUT"
    assert SendResultStatus.SEND_FAILED == "SEND_FAILED"

    bot_instance = AlibabaMessengerBot()
    assert hasattr(bot_instance, "start")
    assert hasattr(bot_instance, "send_message")
    assert hasattr(bot_instance, "check_and_handle_login")
    assert hasattr(bot_instance, "get_recent_conversations")
    assert hasattr(bot_instance, "get_chat_history")
    assert hasattr(bot_instance, "close")

