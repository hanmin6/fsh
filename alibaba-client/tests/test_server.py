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
