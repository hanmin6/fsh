import pytest
from alibaba_messenger.alibaba_bot import AlibabaMessengerBot, SendResultStatus

def test_bot_interface_contracts():
    assert SendResultStatus.SENT == "SENT"
    assert SendResultStatus.BUYER_NOT_FOUND == "BUYER_NOT_FOUND"
    assert SendResultStatus.DUPLICATE_IGNORED == "DUPLICATE_IGNORED"
    assert SendResultStatus.NEED_LOGIN == "NEED_LOGIN"
    assert SendResultStatus.QUEUE_TIMEOUT == "QUEUE_TIMEOUT"
    assert SendResultStatus.SEND_FAILED == "SEND_FAILED"

    bot = AlibabaMessengerBot()
    assert bot.is_logged_in is False
    assert bot.is_busy is False

@pytest.mark.asyncio
async def test_bot_send_when_not_logged_in():
    bot = AlibabaMessengerBot()
    bot.is_logged_in = False
    res = await bot.send_message("Test Buyer", "Hello")
    assert res["success"] is False
    assert res["status"] == SendResultStatus.NEED_LOGIN
