# -*- coding: utf-8 -*-
import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient

from alibaba_messenger.server import app
from alibaba_messenger.alibaba_bot import bot, AlibabaMessengerBot

client = TestClient(app)

def test_get_conversations_unauthenticated():
    """未登录时调用 GET /api/conversations 应返回 401 NEED_LOGIN"""
    original_state = bot.is_logged_in
    try:
        bot.is_logged_in = False
        response = client.get("/api/conversations")
        assert response.status_code == 401
        data = response.json()
        assert data["code"] == 401
        assert data["success"] is False
        assert data["status"] == "NEED_LOGIN"
    finally:
        bot.is_logged_in = original_state

def test_get_history_unauthenticated():
    """未登录时调用 GET /api/message/history 应返回 401 NEED_LOGIN"""
    original_state = bot.is_logged_in
    try:
        bot.is_logged_in = False
        response = client.get("/api/message/history?buyer_name=Alice")
        assert response.status_code == 401
        data = response.json()
        assert data["code"] == 401
        assert data["success"] is False
        assert data["status"] == "NEED_LOGIN"
    finally:
        bot.is_logged_in = original_state

def test_get_history_validation_missing_buyer():
    """缺少 buyer_name 参数应返回 422 验证错误"""
    response = client.get("/api/message/history")
    assert response.status_code == 422

@pytest.mark.asyncio
async def test_bot_get_recent_conversations_mock():
    """验证 bot.get_recent_conversations 提取会话列表契约"""
    bot_instance = AlibabaMessengerBot()
    bot_instance.is_logged_in = True
    
    mock_item = AsyncMock()
    mock_name_el = AsyncMock()
    mock_name_el.inner_text.return_value = "Global Trader Co"
    mock_msg_el = AsyncMock()
    mock_msg_el.inner_text.return_value = "Can you send the quote?"
    mock_time_el = AsyncMock()
    mock_time_el.inner_text.return_value = "10:30"
    mock_badge_el = AsyncMock()
    mock_badge_el.inner_text.return_value = "2"
    
    async def fake_query_selector(selector):
        if "name" in selector or "title" in selector or "buyer" in selector:
            return mock_name_el
        elif "snippet" in selector or "text" in selector or "msg" in selector or "preview" in selector:
            return mock_msg_el
        elif "time" in selector or "date" in selector:
            return mock_time_el
        elif "badge" in selector or "unread" in selector:
            return mock_badge_el
        return None

    mock_item.query_selector = AsyncMock(side_effect=fake_query_selector)

    mock_page = AsyncMock()
    mock_page.query_selector_all.return_value = [mock_item]
    bot_instance.page = mock_page

    result = await bot_instance.get_recent_conversations(limit=10)
    assert result["success"] is True
    assert "conversations" in result["data"]
    assert len(result["data"]["conversations"]) == 1
    conv = result["data"]["conversations"][0]
    assert conv["buyer_name"] == "Global Trader Co"
    assert conv["last_message"] == "Can you send the quote?"
    assert conv["last_time"] == "10:30"
    assert conv["unread_count"] == 2
    assert conv["has_unread"] is True

@pytest.mark.asyncio
async def test_bot_get_chat_history_mock():
    """验证 bot.get_chat_history 提取气泡契约"""
    bot_instance = AlibabaMessengerBot()
    bot_instance.is_logged_in = True
    
    # 模拟搜索联系人成功
    mock_search_input = AsyncMock()
    mock_result_item = AsyncMock()
    
    # 模拟两个气泡：一个是买家发言，一个是我方发言
    bubble1 = AsyncMock()
    bubble1.get_attribute = AsyncMock(return_value="im-message-item bubble-left")
    b1_text = AsyncMock()
    b1_text.inner_text.return_value = "Hello, do you have stock?"
    b1_time = AsyncMock()
    b1_time.inner_text.return_value = "09:00"
    
    bubble2 = AsyncMock()
    bubble2.get_attribute = AsyncMock(return_value="im-message-item bubble-right message-bubble mine")
    b2_text = AsyncMock()
    b2_text.inner_text.return_value = "Yes, we have 500 pcs."
    b2_time = AsyncMock()
    b2_time.inner_text.return_value = "09:05"

    async def b1_qs(selector):
        if "text" in selector or "content" in selector:
            return b1_text
        if "time" in selector:
            return b1_time
        return None
    bubble1.query_selector = AsyncMock(side_effect=b1_qs)

    async def b2_qs(selector):
        if "text" in selector or "content" in selector:
            return b2_text
        if "time" in selector:
            return b2_time
        return None
    bubble2.query_selector = AsyncMock(side_effect=b2_qs)

    mock_page = AsyncMock()
    mock_page.wait_for_selector.side_effect = [mock_search_input, mock_result_item]
    mock_page.query_selector_all.return_value = [bubble1, bubble2]
    bot_instance.page = mock_page

    result = await bot_instance.get_chat_history(buyer_name="Global Trader Co", limit=10)
    assert result["success"] is True
    assert result["data"]["buyer_name"] == "Global Trader Co"
    messages = result["data"]["messages"]
    assert len(messages) == 2
    assert messages[0]["sender"] == "buyer"
    assert messages[0]["content"] == "Hello, do you have stock?"
    assert messages[0]["time"] == "09:00"
    assert messages[1]["sender"] == "seller"
    assert messages[1]["content"] == "Yes, we have 500 pcs."
    assert messages[1]["time"] == "09:05"

@pytest.mark.asyncio
async def test_bot_get_recent_conversations_inquiry_table_mock():
    """验证从阿里国际站商机沟通表格提取商机记录"""
    bot_instance = AlibabaMessengerBot()
    bot_instance.is_logged_in = True
    
    mock_inquiries = [
        {
            "buyer_name": "Oleg Martynenko",
            "inquiry_id": "13907077489",
            "last_message": "In... I've checked the sample...",
            "last_time": "11:24",
            "create_time": "10:57",
            "status": "洽谈中",
            "category": "TM 商机",
            "unread_count": 0,
            "has_unread": False
        },
        {
            "buyer_name": "rotna chan",
            "inquiry_id": "13916589040",
            "last_message": "In... The order quantity is 1000 pcs...",
            "last_time": "10:01",
            "create_time": "2026-9-19",
            "status": "待回复",
            "category": "TM 商机",
            "unread_count": 1,
            "has_unread": True
        }
    ]
    
    mock_page = AsyncMock()
    mock_page.evaluate = AsyncMock(return_value=mock_inquiries)
    bot_instance.page = mock_page

    result = await bot_instance.get_recent_conversations(limit=10)
    assert result["success"] is True
    assert result["data"]["total"] == 2
    convs = result["data"]["conversations"]
    assert convs[0]["buyer_name"] == "Oleg Martynenko"
    assert convs[0]["inquiry_id"] == "13907077489"
    assert convs[0]["status"] == "洽谈中"
    assert convs[1]["buyer_name"] == "rotna chan"
    assert convs[1]["has_unread"] is True

def test_get_history_validation_inquiry_id_accepted():
    """提供 inquiry_id 而不提供 buyer_name 时不应报 422 验证错误"""
    original_state = bot.is_logged_in
    try:
        bot.is_logged_in = False
        # 未登录时验证已通过，返回 401 而非 422
        response = client.get("/api/message/history?inquiry_id=13907077489")
        assert response.status_code == 401
    finally:
        bot.is_logged_in = original_state


@pytest.mark.asyncio
async def test_get_all_conversations_stops_on_empty_or_repeated_page():
    bot_instance = AlibabaMessengerBot()
    pages = [
        [{"inquiry_id": "100"}, {"inquiry_id": "101"}],
        [{"inquiry_id": "102"}],
        [],
    ]

    async def read_page(limit=1000):
        return {"success": True, "data": {"conversations": pages.pop(0)}}

    bot_instance.get_recent_conversations = read_page
    bot_instance._navigate_conversation_page = AsyncMock(return_value=True)
    assert [item["inquiry_id"] for item in await bot_instance.get_all_conversations()] == ["100", "101", "102"]
    assert bot_instance._navigate_conversation_page.await_count == 2


@pytest.mark.asyncio
async def test_navigate_conversation_page_clicks_next_button():
    bot = AlibabaMessengerBot()
    mock_page = AsyncMock()
    mock_btn = AsyncMock()
    mock_btn.is_visible.return_value = True
    mock_btn.get_attribute.return_value = None  # not disabled

    # First query for page numbers fails, next button succeeds
    async def fake_query(selector):
        if "next-next" in selector:
            return mock_btn
        return None

    mock_page.query_selector.side_effect = fake_query
    bot.page = mock_page

    result = await bot._navigate_conversation_page(2)
    assert result is True
    mock_btn.click.assert_called_once()



@pytest.mark.asyncio
async def test_get_sync_history_converts_and_filters_system_messages():
    bot_instance = AlibabaMessengerBot()
    bot_instance.get_chat_history = AsyncMock(return_value={"success": True, "data": {"messages": [
        {"sender": "buyer", "content": " hello\r\nthere ", "time": "2026-09-21 10:00", "type": "initial_inquiry"},
        {"sender": "system", "content": "notice", "time": "2026-09-21 10:01"},
        {"sender": "seller", "content": "reply", "time": "10:02", "platform_id": "message-2"},
    ]}})
    messages = await bot_instance.get_sync_history("123")
    assert [message.direction for message in messages] == ["inbound", "outbound"]
    assert messages[0].body == "hello\nthere"
    assert messages[0].message_type == "initialInquiry"
    assert messages[1].external_id == "message-2"

@pytest.mark.asyncio
async def test_extract_dialogue_messages_ordering():
    """验证 _extract_dialogue_messages 的时间排序与 limit 逻辑"""
    bot_instance = AlibabaMessengerBot()
    
    # 模拟 evaluate 返回的数据（DOM中常见降序：新消息在前，旧消息在后）
    mock_extracted = {
        "initialCard": {
            "sender": "buyer",
            "content": "询盘产品: Native Potato Starch 70000kg",
            "time": "10:57",
            "type": "initial_inquiry"
        },
        "bubbles": [
            {"sender": "buyer", "content": "I've passed", "time": "11:26"},
            {"sender": "seller", "content": "I have added you", "time": "11:24"},
            {"sender": "buyer", "content": "19700172045", "time": "11:23"},
            {"sender": "seller", "content": "Thank you for the volume", "time": "11:01"}
        ]
    }

    mock_page = AsyncMock()
    # evaluate 会被调用两次：第一次是自动滚动/展开历史，第二次是提取
    mock_page.evaluate = AsyncMock(side_effect=[False, mock_extracted])

    # 1. limit=0 (获取完整所有会话)
    res_all = await bot_instance._extract_dialogue_messages(mock_page, limit=0, order="asc")
    assert len(res_all) == 5
    # 首条应为原始询盘卡片
    assert res_all[0]["type"] == "initial_inquiry"
    # 气泡应已反转为时间正序 (11:01 -> 11:23 -> 11:24 -> 11:26)
    assert res_all[1]["time"] == "11:01"
    assert res_all[2]["time"] == "11:23"
    assert res_all[3]["time"] == "11:24"
    assert res_all[4]["time"] == "11:26"

    # 2. limit=2 (获取最新的 2 条记录)
    mock_page.evaluate = AsyncMock(side_effect=[False, mock_extracted])
    res_limit2 = await bot_instance._extract_dialogue_messages(mock_page, limit=2, order="asc")
    assert len(res_limit2) == 2
    assert res_limit2[0]["time"] == "11:24"
    assert res_limit2[1]["time"] == "11:26"


@pytest.mark.asyncio
async def test_iter_conversations_pages_yields_page_by_page():
    bot_instance = AlibabaMessengerBot()
    pages = [
        [{"inquiry_id": "100", "buyer_name": "Buyer 1"}, {"inquiry_id": "101", "buyer_name": "Buyer 2"}],
        [{"inquiry_id": "102", "buyer_name": "Buyer 3"}],
        [],
    ]

    async def read_page(limit=1000):
        return {"success": True, "data": {"conversations": pages.pop(0)}}

    bot_instance.get_recent_conversations = read_page
    bot_instance._navigate_conversation_page = AsyncMock(return_value=True)

    collected_pages = []
    async for page_items in bot_instance.iter_conversations_pages():
        collected_pages.append(page_items)

    assert len(collected_pages) == 2
    assert [x["inquiry_id"] for x in collected_pages[0]] == ["100", "101"]
    assert [x["inquiry_id"] for x in collected_pages[1]] == ["102"]
    assert bot_instance._navigate_conversation_page.await_count == 2


@pytest.mark.asyncio
async def test_bot_get_recent_conversations_im_fallback_includes_country():
    """验证 IM 备选分支提取最近会话时包含 country 字段"""
    bot_instance = AlibabaMessengerBot()
    bot_instance.is_logged_in = True
    bot_instance.page = AsyncMock()
    # evaluate returns empty to trigger IM fallback
    bot_instance.page.evaluate.return_value = []

    mock_item = AsyncMock()
    mock_name_el = AsyncMock()
    mock_name_el.inner_text = AsyncMock(return_value="US Buyer Corp")
    mock_country_el = AsyncMock()
    mock_country_el.inner_text = AsyncMock(return_value="United States")

    async def fake_query_selector(selector):
        if "name" in selector or "title" in selector:
            return mock_name_el
        if "country" in selector or "flag" in selector or "region" in selector:
            return mock_country_el
        return None

    mock_item.query_selector = AsyncMock(side_effect=fake_query_selector)
    bot_instance.page.query_selector_all.return_value = [mock_item]

    result = await bot_instance.get_recent_conversations(limit=5)
    assert result["success"] is True
    convs = result["data"]["conversations"]
    assert len(convs) == 1
    assert "country" in convs[0]
    assert convs[0]["country"] == "United States"


@pytest.mark.asyncio
async def test_bot_find_inquiry_row_returns_country_and_caches():
    """验证 _find_inquiry_row 返回 country 字段并在 bot 内部缓存"""
    bot_instance = AlibabaMessengerBot()
    bot_instance.page = AsyncMock()
    bot_instance._get_current_page_number = AsyncMock(return_value=1)
    
    bot_instance.page.evaluate.return_value = {
        "found": True,
        "index": 0,
        "buyer_name": "Alice Smith",
        "inquiry_id": "999888",
        "country": "Germany",
        "last_message": "Price inquiry",
        "last_time": "12:00",
        "href": "/inquiry/detail.htm?id=999888",
        "target": "_blank"
    }

    res, page_num = await bot_instance._find_inquiry_row(inquiry_id="999888")
    assert res is not None
    assert res.get("country") == "Germany"
    assert bot_instance.get_last_extracted_country("999888") == "Germany"


@pytest.mark.asyncio
async def test_bot_get_chat_history_includes_country():
    """验证 bot.get_chat_history 返回数据包含 country 字段"""
    bot_instance = AlibabaMessengerBot()
    bot_instance.is_logged_in = True
    bot_instance._find_inquiry_row = AsyncMock(return_value=({
        "found": True,
        "index": 0,
        "buyer_name": "Bob Stone",
        "inquiry_id": "777666",
        "country": "France",
        "last_message": "Can we talk?",
        "last_time": "14:00",
        "href": "",
        "target": ""
    }, 1))

    # mock dialogue messages extraction
    bot_instance._extract_dialogue_messages = AsyncMock(return_value=[
        {"sender": "buyer", "content": "Can we talk?", "time": "14:00"}
    ])

    res = await bot_instance.get_chat_history(inquiry_id="777666")
    assert res["success"] is True
    assert "country" in res["data"]
    assert res["data"]["country"] == "France"
    assert bot_instance.get_last_extracted_country("777666") == "France"


@pytest.mark.asyncio
async def test_bot_get_buyer_profile():
    """验证 bot.get_buyer_profile 获取买家资料及国家"""
    bot_instance = AlibabaMessengerBot()
    bot_instance.is_logged_in = True
    bot_instance._find_inquiry_row = AsyncMock(return_value=({
        "found": True,
        "index": 0,
        "buyer_name": "Carol Danvers",
        "inquiry_id": "555444",
        "country": "Canada",
        "last_message": "Need specs",
        "last_time": "15:30"
    }, 1))

    res = await bot_instance.get_buyer_profile(inquiry_id="555444")
    assert res["success"] is True
    assert res["data"]["buyer_name"] == "Carol Danvers"
    assert res["data"]["inquiry_id"] == "555444"
    assert res["data"]["country"] == "Canada"
    assert bot_instance.get_last_extracted_country("555444") == "Canada"


