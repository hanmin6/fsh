from fastapi.testclient import TestClient
from alibaba_messenger.server import app

client = TestClient(app)

def test_get_status_endpoint():
    response = client.get("/api/status")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert data["code"] == 200
    assert "data" in data
    assert "is_logged_in" in data["data"]

def test_send_message_validation():
    # 缺少 message 字段应触发 422 验证错误
    response = client.post("/api/message/send", json={"buyer_name": "John"})
    assert response.status_code == 422

def test_send_message_unauthenticated():
    # 在未登录状态下发信应返回 401 NEED_LOGIN
    response = client.post("/api/message/send", json={"buyer_name": "John", "message": "Hi"})
    assert response.status_code == 401
    data = response.json()
    assert data["status"] == "NEED_LOGIN"


def test_buyer_profile_validation():
    # 缺少 buyer_name 与 inquiry_id 应返回 422
    response = client.get("/api/buyer/profile")
    assert response.status_code == 422


def test_buyer_profile_unauthenticated():
    from alibaba_messenger.alibaba_bot import bot
    original = bot.is_logged_in
    try:
        bot.is_logged_in = False
        response = client.get("/api/buyer/profile?inquiry_id=12345")
        assert response.status_code == 401
        data = response.json()
        assert data["status"] == "NEED_LOGIN"
    finally:
        bot.is_logged_in = original


def test_crm_client_extract_order_country():
    from alibaba_crm_client import AlibabaCRMClient
    order_data1 = {
        "logistics_address": {
            "country_name": "United States",
            "country": "US"
        }
    }
    assert AlibabaCRMClient.extract_order_country(order_data1) == "United States"

    order_data2 = {
        "buyer_info": {
            "country": "DE"
        }
    }
    assert AlibabaCRMClient.extract_order_country(order_data2) == "DE"

    order_data3 = {
        "shipping_address": {
            "country": "Japan"
        }
    }
    assert AlibabaCRMClient.extract_order_country(order_data3) == "Japan"


def test_api_health_endpoint():
    from alibaba_messenger.alibaba_bot import bot
    original = bot.is_logged_in
    try:
        bot.is_logged_in = True
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "data" in data
        assert data["data"]["status"] == "UP"
        assert data["data"]["is_logged_in"] is True
        assert "last_keep_alive" in data["data"]
    finally:
        bot.is_logged_in = original


def test_api_session_keepalive_endpoint():
    from unittest.mock import AsyncMock
    from alibaba_messenger.alibaba_bot import bot
    original_keep = getattr(bot, "keep_alive", None)
    try:
        bot.keep_alive = AsyncMock(return_value=True)
        response = client.post("/api/session/keepalive", json={"force_reload": False})
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        bot.keep_alive.assert_called_once_with(force_reload=False)
    finally:
        if original_keep:
            bot.keep_alive = original_keep


def test_api_session_refresh_endpoint():
    from unittest.mock import AsyncMock
    from alibaba_messenger.alibaba_bot import bot
    original_keep = getattr(bot, "keep_alive", None)
    try:
        bot.keep_alive = AsyncMock(return_value=True)
        response = client.post("/api/session/refresh")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        bot.keep_alive.assert_called_once_with(force_reload=True)
    finally:
        if original_keep:
            bot.keep_alive = original_keep

