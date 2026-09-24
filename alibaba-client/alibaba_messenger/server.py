# -*- coding: utf-8 -*-
import asyncio
from contextlib import asynccontextmanager
from typing import Optional, Dict, Any
from fastapi import FastAPI, Response, status, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from alibaba_messenger.config import settings
from alibaba_messenger.alibaba_bot import bot, SendResultStatus

# 单浏览器操作排队锁
browser_lock = asyncio.Lock()
waiting_counter = 0

class SendMessageRequest(BaseModel):
    buyer_name: str = Field(..., description="买家姓名/旺旺名/公司名")
    message: str = Field(..., description="待发送的问候内容")
    inquiry_id: Optional[str] = Field(None, description="商机询价单号 (可选)")
    force_send: bool = Field(False, description="是否强制发送(跳过防重)")
    timeout_seconds: int = Field(30, description="最大等待与执行超时(秒)")

class KeepAliveRequest(BaseModel):
    force_reload: bool = Field(False, description="是否强制重新加载页面")
    timeout_seconds: int = Field(settings.DEFAULT_QUEUE_TIMEOUT_SEC, description="排队超时时间(秒)")

class APIResponse(BaseModel):
    code: int
    success: bool
    status: str
    message: str
    data: Optional[Dict[str, Any]] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await bot.close()

app = FastAPI(
    title="Alibaba Messenger API",
    description="阿里巴巴国际站自动发消息服务 API (供 CRM 调用)",
    version="1.0.0",
    lifespan=lifespan
)

@app.get("/api/status", response_model=APIResponse)
async def get_status():
    status_str = "READY"
    if not bot.is_logged_in:
        status_str = "NEED_LOGIN"
    elif bot.is_busy:
        status_str = "BUSY"

    return APIResponse(
        code=200,
        success=True,
        status=status_str,
        message="服务正常运行",
        data={
            "is_logged_in": bot.is_logged_in,
            "is_busy": bot.is_busy,
            "waiting_queue_count": waiting_counter
        }
    )

@app.get("/api/health", response_model=APIResponse)
async def get_health():
    """获取服务与阿里国际站会话健康状态"""
    is_healthy = bot.is_logged_in
    status_str = "UP" if is_healthy else "DEGRADED"

    url = ""
    if bot.page and not bot.page.is_closed():
        try:
            url = bot.page.url
        except Exception:
            pass

    return APIResponse(
        code=200,
        success=True,
        status=status_str,
        message="服务状态健康" if is_healthy else "服务运行中但国际站会话需重新登录",
        data={
            "status": status_str,
            "is_logged_in": bot.is_logged_in,
            "is_busy": bot.is_busy,
            "last_keep_alive": getattr(bot, "_last_keep_alive", 0),
            "last_refresh_time": getattr(bot, "_last_refresh_time", 0),
            "page_url": url,
            "waiting_queue_count": waiting_counter
        }
    )

@app.post("/api/session/keepalive", response_model=APIResponse)
async def session_keepalive(req: Optional[KeepAliveRequest] = None):
    """保活巡检接口：检查连接并可选择强制刷新商机列表"""
    force_reload = req.force_reload if req else False
    timeout_sec = req.timeout_seconds if req else settings.DEFAULT_QUEUE_TIMEOUT_SEC

    global waiting_counter
    waiting_counter += 1
    try:
        try:
            await asyncio.wait_for(browser_lock.acquire(), timeout=timeout_sec)
        except asyncio.TimeoutError:
            return JSONResponse(
                status_code=429,
                content={
                    "code": 429,
                    "success": False,
                    "status": SendResultStatus.QUEUE_TIMEOUT.value,
                    "message": "前序任务执行繁忙，排队超时",
                    "data": None
                }
            )

        try:
            alive = await bot.keep_alive(force_reload=force_reload)
            http_status = 200 if alive else 401
            return JSONResponse(
                status_code=http_status,
                content={
                    "code": http_status,
                    "success": alive,
                    "status": "READY" if alive else "NEED_LOGIN",
                    "message": "会话保活正常" if alive else "会话已失效或需要登录",
                    "data": {
                        "is_logged_in": bot.is_logged_in,
                        "last_keep_alive": getattr(bot, "_last_keep_alive", 0),
                        "last_refresh_time": getattr(bot, "_last_refresh_time", 0)
                    }
                }
            )
        finally:
            browser_lock.release()
    finally:
        waiting_counter = max(0, waiting_counter - 1)

@app.post("/api/session/refresh", response_model=APIResponse)
async def session_refresh():
    """主动刷新商机沟通页面以拉取最新会话列表并激活长连接"""
    global waiting_counter
    waiting_counter += 1
    try:
        try:
            await asyncio.wait_for(browser_lock.acquire(), timeout=settings.DEFAULT_QUEUE_TIMEOUT_SEC)
        except asyncio.TimeoutError:
            return JSONResponse(
                status_code=429,
                content={
                    "code": 429,
                    "success": False,
                    "status": SendResultStatus.QUEUE_TIMEOUT.value,
                    "message": "前序任务执行繁忙，排队超时",
                    "data": None
                }
            )

        try:
            alive = await bot.keep_alive(force_reload=True)
            http_status = 200 if alive else 401
            return JSONResponse(
                status_code=http_status,
                content={
                    "code": http_status,
                    "success": alive,
                    "status": "READY" if alive else "NEED_LOGIN",
                    "message": "商机沟通页面已刷新就绪" if alive else "会话已失效或需要登录",
                    "data": {
                        "is_logged_in": bot.is_logged_in,
                        "last_refresh_time": getattr(bot, "_last_refresh_time", 0)
                    }
                }
            )
        finally:
            browser_lock.release()
    finally:
        waiting_counter = max(0, waiting_counter - 1)

@app.post("/api/login/check", response_model=APIResponse)
async def check_login():
    logged_in = await bot.check_and_handle_login()
    http_status = 200 if logged_in else 401
    content = {
        "code": http_status,
        "success": logged_in,
        "status": "READY" if logged_in else "NEED_LOGIN",
        "message": "登录态有效" if logged_in else "尚未登录或登录已失效",
        "data": {"is_logged_in": logged_in}
    }
    return JSONResponse(status_code=http_status, content=content)

@app.post("/api/message/send", response_model=APIResponse)
async def send_message(req: SendMessageRequest):
    global waiting_counter
    waiting_counter += 1
    
    try:
        # 获取排队互斥锁
        try:
            await asyncio.wait_for(browser_lock.acquire(), timeout=req.timeout_seconds)
        except asyncio.TimeoutError:
            return JSONResponse(
                status_code=429,
                content={
                    "code": 429,
                    "success": False,
                    "status": SendResultStatus.QUEUE_TIMEOUT.value,
                    "message": "前序消息发送繁忙，排队超时",
                    "data": {"buyer_name": req.buyer_name}
                }
            )

        try:
            # 委托机器人执行
            res = await bot.send_message(
                buyer_name=req.buyer_name,
                message=req.message,
                inquiry_id=req.inquiry_id,
                force_send=req.force_send
            )
            
            http_status = 200
            res_status = res["status"]
            if res_status == SendResultStatus.BUYER_NOT_FOUND:
                http_status = 404
            elif res_status == SendResultStatus.DUPLICATE_IGNORED:
                http_status = 409
            elif res_status == SendResultStatus.NEED_LOGIN:
                http_status = 401
            elif res_status == SendResultStatus.SEND_FAILED:
                http_status = 500

            return JSONResponse(
                status_code=http_status,
                content={
                    "code": http_status,
                    "success": res["success"],
                    "status": res["status"].value if hasattr(res["status"], "value") else str(res["status"]),
                    "message": res["message"],
                    "data": res.get("data")
                }
            )
        finally:
            browser_lock.release()
            
    finally:
        waiting_counter = max(0, waiting_counter - 1)

@app.get("/api/conversations", response_model=APIResponse)
async def get_conversations(
    limit: int = Query(20, ge=1, le=100, description="拉取最近会话数量"),
    timeout_seconds: int = Query(settings.DEFAULT_QUEUE_TIMEOUT_SEC, description="排队超时时间(秒)")
):
    """获取消息中心最近会话列表及未读标记"""
    if not bot.is_logged_in:
        return JSONResponse(
            status_code=401,
            content={
                "code": 401,
                "success": False,
                "status": SendResultStatus.NEED_LOGIN.value,
                "message": "国际站尚未登录，请先在界面完成登录",
                "data": {"conversations": []}
            }
        )

    global waiting_counter
    waiting_counter += 1
    try:
        try:
            await asyncio.wait_for(browser_lock.acquire(), timeout=timeout_seconds)
        except asyncio.TimeoutError:
            return JSONResponse(
                status_code=429,
                content={
                    "code": 429,
                    "success": False,
                    "status": SendResultStatus.QUEUE_TIMEOUT.value,
                    "message": "前序任务执行繁忙，排队超时",
                    "data": {"conversations": []}
                }
            )

        try:
            res = await bot.get_recent_conversations(limit=limit)
            http_status = 200 if res["success"] else 500
            return JSONResponse(
                status_code=http_status,
                content={
                    "code": http_status,
                    "success": res["success"],
                    "status": res["status"] if isinstance(res["status"], str) else res["status"].value,
                    "message": res["message"],
                    "data": res.get("data")
                }
            )
        finally:
            browser_lock.release()
    finally:
        waiting_counter = max(0, waiting_counter - 1)

@app.get("/api/message/history", response_model=APIResponse)
async def get_message_history(
    buyer_name: Optional[str] = Query(None, description="买家名称/旺旺名/公司名"),
    inquiry_id: Optional[str] = Query(None, description="商机询价单号 (与 buyer_name 二选一)"),
    limit: int = Query(0, ge=0, le=1000, description="拉取历史消息气泡最大条数 (0表示获取全部完整会话记录)"),
    order: str = Query("asc", pattern="^(asc|desc)$", description="消息排序方式: asc(时间正序/从旧到新), desc(时间倒序/从新到旧)"),
    timeout_seconds: int = Query(settings.DEFAULT_QUEUE_TIMEOUT_SEC, description="排队超时时间(秒)")
):
    """进入指定买家会话或商机ID，读取完整历史往来记录"""
    if not buyer_name and not inquiry_id:
        return JSONResponse(
            status_code=422,
            content={
                "code": 422,
                "success": False,
                "status": "VALIDATION_ERROR",
                "message": "参数错误：必须提供 buyer_name 或 inquiry_id 之一",
                "data": None
            }
        )

    if not bot.is_logged_in:
        return JSONResponse(
            status_code=401,
            content={
                "code": 401,
                "success": False,
                "status": SendResultStatus.NEED_LOGIN.value,
                "message": "国际站尚未登录，请先在界面完成登录",
                "data": {"buyer_name": buyer_name or "", "inquiry_id": inquiry_id or "", "messages": []}
            }
        )

    global waiting_counter
    waiting_counter += 1
    try:
        try:
            await asyncio.wait_for(browser_lock.acquire(), timeout=timeout_seconds)
        except asyncio.TimeoutError:
            return JSONResponse(
                status_code=429,
                content={
                    "code": 429,
                    "success": False,
                    "status": SendResultStatus.QUEUE_TIMEOUT.value,
                    "message": "前序任务执行繁忙，排队超时",
                    "data": {"buyer_name": buyer_name or "", "inquiry_id": inquiry_id or "", "messages": []}
                }
            )

        try:
            res = await bot.get_chat_history(buyer_name=buyer_name, inquiry_id=inquiry_id, limit=limit, order=order)
            http_status = 200
            res_status = res["status"]
            if res_status == SendResultStatus.BUYER_NOT_FOUND:
                http_status = 404
            elif res_status == SendResultStatus.NEED_LOGIN:
                http_status = 401
            elif res_status == SendResultStatus.SEND_FAILED:
                http_status = 500

            return JSONResponse(
                status_code=http_status,
                content={
                    "code": http_status,
                    "success": res["success"],
                    "status": res["status"] if isinstance(res["status"], str) else res["status"].value,
                    "message": res["message"],
                    "data": res.get("data")
                }
            )
        finally:
            browser_lock.release()
    finally:
        waiting_counter = max(0, waiting_counter - 1)

@app.get("/api/buyer/profile", response_model=APIResponse)
async def get_buyer_profile(
    buyer_name: Optional[str] = Query(None, description="买家名称/旺旺名/公司名"),
    inquiry_id: Optional[str] = Query(None, description="商机询价单号 (与 buyer_name 二选一)"),
    timeout_seconds: int = Query(settings.DEFAULT_QUEUE_TIMEOUT_SEC, description="排队超时时间(秒)")
):
    """获取指定买家或商机ID的资料（包括国家/地区、姓名等）"""
    if not buyer_name and not inquiry_id:
        return JSONResponse(
            status_code=422,
            content={
                "code": 422,
                "success": False,
                "status": "VALIDATION_ERROR",
                "message": "参数错误：必须提供 buyer_name 或 inquiry_id 之一",
                "data": None
            }
        )

    if not bot.is_logged_in:
        return JSONResponse(
            status_code=401,
            content={
                "code": 401,
                "success": False,
                "status": SendResultStatus.NEED_LOGIN.value,
                "message": "国际站尚未登录，请先在界面完成登录",
                "data": {"buyer_name": buyer_name or "", "inquiry_id": inquiry_id or "", "country": ""}
            }
        )

    global waiting_counter
    waiting_counter += 1
    try:
        try:
            await asyncio.wait_for(browser_lock.acquire(), timeout=timeout_seconds)
        except asyncio.TimeoutError:
            return JSONResponse(
                status_code=429,
                content={
                    "code": 429,
                    "success": False,
                    "status": SendResultStatus.QUEUE_TIMEOUT.value,
                    "message": "前序任务执行繁忙，排队超时",
                    "data": {"buyer_name": buyer_name or "", "inquiry_id": inquiry_id or "", "country": ""}
                }
            )

        try:
            res = await bot.get_buyer_profile(buyer_name=buyer_name, inquiry_id=inquiry_id)
            http_status = 200
            res_status = res["status"]
            if res_status == SendResultStatus.BUYER_NOT_FOUND:
                http_status = 404
            elif res_status == SendResultStatus.NEED_LOGIN:
                http_status = 401

            return JSONResponse(
                status_code=http_status,
                content={
                    "code": http_status,
                    "success": res["success"],
                    "status": res["status"] if isinstance(res["status"], str) else res["status"].value,
                    "message": res["message"],
                    "data": res.get("data")
                }
            )
        finally:
            browser_lock.release()
    finally:
        waiting_counter = max(0, waiting_counter - 1)

@app.get("/api/debug/screenshot")
async def debug_screenshot(page_index: int = Query(0, description="页面索引")):
    """调试端点：截取指定浏览器画面并返回页面URL与标题"""
    import time
    import os
    path = os.path.join(settings.SCREENSHOTS_DIR, f"manual_debug_{int(time.time())}.png")
    target_page = bot.page
    if bot.context and bot.context.pages and 0 <= page_index < len(bot.context.pages):
        target_page = bot.context.pages[page_index]
    
    if target_page:
        await target_page.screenshot(path=path)
        title = await target_page.title()
        url = target_page.url
        pages_count = len(bot.context.pages) if bot.context else 0
        pages_urls = [p.url for p in bot.context.pages] if bot.context else []
        return {
            "success": True,
            "url": url,
            "title": title,
            "pages_count": pages_count,
            "pages_urls": pages_urls,
            "path": path
        }
    return {"success": False, "error": "No valid page"}

@app.get("/api/debug/dump_row")
async def debug_dump_row():
    """调试端点：获取第一条商机卡片的完整文本结构与子元素列表"""
    if not bot.page:
        return {"error": "no page"}
    data = await bot.page.evaluate("""
    () => {
        const link = Array.from(document.querySelectorAll("a, button, span")).find(el => el.innerText && el.innerText.trim() === "查看详情");
        if (!link) return { error: "no 查看详情 link found" };
        let cur = link;
        let row = null;
        while (cur && cur !== document.body) {
            if (cur.innerText && cur.innerText.includes("询价单号")) {
                row = cur;
                if (cur.parentElement && (cur.parentElement.innerText.match(/询价单号/g) || []).length > 1) break;
            }
            cur = cur.parentElement;
        }
        if (!row) return { error: "no row found" };
        const children = Array.from(row.querySelectorAll("*")).map(e => ({
            tag: e.tagName,
            className: String(e.className),
            text: e.innerText ? e.innerText.trim() : "",
            childrenCount: e.children.length
        })).filter(e => e.childrenCount === 0 && e.text.length > 0);
        return {
            rawText: row.innerText,
            leafNodes: children
        };
    }
    """)
    return data



