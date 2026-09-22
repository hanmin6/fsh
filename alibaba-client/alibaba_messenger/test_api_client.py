# -*- coding: utf-8 -*-
"""
CRM 模拟客户端示例脚本：向本地 Playwright 消息自动化服务发起请求
支持：
  1. 状态探活 (GET /api/status)
  2. 发送单条问候消息 (POST /api/message/send)
  3. 触发登录检测 (POST /api/login/check)
  4. 获取最近会话列表 (GET /api/conversations)
  5. 获取买家聊天历史 (GET /api/message/history)
"""

import requests
import json

BASE_URL = "http://127.0.0.1:8000"

def get_server_status():
    """探活接口"""
    url = f"{BASE_URL}/api/status"
    try:
        r = requests.get(url, timeout=5)
        print("\n[CRM -> Status] 状态探活响应:")
        print(json.dumps(r.json(), ensure_ascii=False, indent=2))
        return r.json()
    except Exception as e:
        print(f"[CRM -> Status] 无法连接到服务: {e}")
        return None

def send_greeting(buyer_name: str, message: str, force_send: bool = False, timeout: int = 30):
    """发送消息接口"""
    url = f"{BASE_URL}/api/message/send"
    payload = {
        "buyer_name": buyer_name,
        "message": message,
        "force_send": force_send,
        "timeout_seconds": timeout
    }
    print(f"\n[CRM -> Send] 正在向买家 [{buyer_name}] 发送消息...")
    try:
        r = requests.post(url, json=payload, timeout=timeout + 5)
        print(f"[CRM -> Send] HTTP状态码: {r.status_code}")
        print(json.dumps(r.json(), ensure_ascii=False, indent=2))
        return r.json()
    except Exception as e:
        print(f"[CRM -> Send] 请求发生异常: {e}")
        return None

def check_login():
    """触发重新检测登录态"""
    url = f"{BASE_URL}/api/login/check"
    try:
        r = requests.post(url, timeout=10)
        print("\n[CRM -> LoginCheck] 登录检测响应:")
        print(json.dumps(r.json(), ensure_ascii=False, indent=2))
        return r.json()
    except Exception as e:
        print(f"[CRM -> LoginCheck] 请求异常: {e}")
        return None

def get_recent_conversations(limit: int = 20):
    """获取最近会话列表及未读标记"""
    url = f"{BASE_URL}/api/conversations?limit={limit}"
    print(f"\n[CRM -> Conversations] 正在拉取最近 {limit} 条会话列表...")
    try:
        r = requests.get(url, timeout=15)
        print(f"[CRM -> Conversations] HTTP状态码: {r.status_code}")
        print(json.dumps(r.json(), ensure_ascii=False, indent=2))
        return r.json()
    except Exception as e:
        print(f"[CRM -> Conversations] 请求异常: {e}")
        return None

def get_message_history(buyer_name: str, limit: int = 50):
    """获取指定买家聊天历史"""
    url = f"{BASE_URL}/api/message/history"
    params = {"buyer_name": buyer_name, "limit": limit}
    print(f"\n[CRM -> History] 正在拉取买家 [{buyer_name}] 的聊天历史...")
    try:
        r = requests.get(url, params=params, timeout=25)
        print(f"[CRM -> History] HTTP状态码: {r.status_code}")
        print(json.dumps(r.json(), ensure_ascii=False, indent=2))
        return r.json()
    except Exception as e:
        print(f"[CRM -> History] 请求异常: {e}")
        return None

if __name__ == "__main__":
    print("=== 模拟 CRM 客户端测试 ===")
    status_info = get_server_status()
    
    # 演示调用（真实执行时解开注释）
    # get_recent_conversations(limit=10)
    # get_message_history(buyer_name="John Smith", limit=20)
    # send_greeting(
    #     buyer_name="John Smith",
    #     message="Dear John, wishing you and your team a wonderful holiday from FSH!",
    #     force_send=False
    # )

