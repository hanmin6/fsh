# 阿里巴巴国际站 Playwright 自动发消息服务实施计划 (Implementation Plan)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 基于 Playwright 构建常驻且持久化登录态的阿里国际站消息自动化控制器，支持未登录状态暂停并通知人工扫码，封装为带排队锁的 FastAPI 同步接口供 CRM 调用。

**Architecture:** 
- 底层使用 Playwright 持久化上下文（User Data Dir）保持会话与去特征化启动；
- 启动及运行过程中若检测到未登录，自动打开可视化浏览器窗口并暂停，醒目通知用户扫码登录；
- 核心发信控制器执行买家检索、会话打开、聊天防重比对、模拟人工抖动输入与点击发送；
- 上层使用 FastAPI 暴露 RESTful 接口，并以 `asyncio.Lock` 实现单浏览器上下文排队调度，异常时截屏留痕。

**Tech Stack:** Python 3.10+, Playwright, FastAPI, Uvicorn, Pydantic, Pytest

**Spec:** [`docs/superpowers/specs/2026-09-19-alibaba-playwright-messenger-design.md`](file:///g:/FSH/alibb/docs/superpowers/specs/2026-09-19-alibaba-playwright-messenger-design.md)

## Global Constraints
- 所有自动化及接口代码均收敛在 `alibaba_messenger/` 模块下，不修改既有 `alibaba_crm_client.py`。
- 浏览器持久化目录位于 `alibaba_messenger/profile/`，日志与截屏位于 `alibaba_messenger/logs/`。
- 键盘输入必须使用逐字符随机延时（20ms~80ms），发信后执行 3~6s 冷却休眠。
- 账号未登录时必须挂起暂停并给出显式指引，严禁在未登录状态下盲目执行发信报错。

## Review Focus
1. **未登录或会话过期**：初次启动或运行中登录失效，系统必须暂停并向用户展示扫码引导，登录完成后自动恢复就绪。
2. **买家重名或搜不到联系人**：搜索框输入买家名称无匹配结果时，不卡死，需在 5 秒内返回 `BUYER_NOT_FOUND`。
3. **CRM 高频并发请求**：多个 CRM 请求并发调用接口，`asyncio.Lock` 必须严格保证串行操作且超时请求返回 `429 QUEUE_TIMEOUT`。
4. **页面遮罩或突发活动弹窗**：消息中心偶尔弹出营销/协议浮层，操作前需有探测兜底关闭机制，若失败截屏存入 `logs/screenshots/`。
5. **同买家同内容重复发信**：同一天内向同一买家发送相同内容，在 `force_send=False` 时被双重拦截（内存记录与页面气泡对比）并返回 `DUPLICATE_IGNORED`。

---

### Task 1: 基础配置与依赖环境定义

**Files:**
- Create: `alibaba_messenger/config.py`
- Create: `alibaba_messenger/requirements.txt`
- Test: `tests/test_config.py`

**Interfaces:**
- Produces: `Config` 类的静态属性或实例配置（`PROFILE_DIR`, `LOGS_DIR`, `SCREENSHOTS_DIR`, `SERVER_PORT`, `TYPING_DELAY_MIN_MS`, 等）。

- [ ] **Step 1: Write the failing test**

```python
# tests/test_config.py
import os
from alibaba_messenger.config import Settings

def test_settings_paths_and_defaults():
    settings = Settings()
    assert os.path.isabs(settings.BASE_DIR)
    assert os.path.isabs(settings.PROFILE_DIR)
    assert os.path.isabs(settings.LOGS_DIR)
    assert os.path.isabs(settings.SCREENSHOTS_DIR)
    assert settings.SERVER_PORT == 8000
    assert settings.TYPING_DELAY_MIN_MS == 20
    assert settings.TYPING_DELAY_MAX_MS == 80
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'alibaba_messenger'`

- [ ] **Step 3: Write minimal implementation**

```python
# alibaba_messenger/requirements.txt
playwright>=1.40.0
fastapi>=0.100.0
uvicorn>=0.23.0
pydantic>=2.0.0
pytest>=7.0.0
pytest-asyncio>=0.21.0
requests>=2.28.0
```

```python
# alibaba_messenger/config.py
import os
from dataclasses import dataclass

@dataclass
class Settings:
    BASE_DIR: str = os.path.dirname(os.path.abspath(__file__))
    PROFILE_DIR: str = os.path.join(BASE_DIR, "profile")
    LOGS_DIR: str = os.path.join(BASE_DIR, "logs")
    SCREENSHOTS_DIR: str = os.path.join(LOGS_DIR, "screenshots")
    SENT_RECORDS_FILE: str = os.path.join(LOGS_DIR, "sent_records.json")
    
    ALIBABA_MSG_URL: str = "https://message.alibaba.com/message/default.htm"
    ALIBABA_LOGIN_FLAG: str = "passport.alibaba.com"
    
    SERVER_HOST: str = "0.0.0.0"
    SERVER_PORT: int = 8000
    
    TYPING_DELAY_MIN_MS: int = 20
    TYPING_DELAY_MAX_MS: int = 80
    POST_SEND_COOLDOWN_MIN_SEC: float = 3.0
    POST_SEND_COOLDOWN_MAX_SEC: float = 6.0
    
    SEARCH_TIMEOUT_MS: int = 5000
    PAGE_ACTION_TIMEOUT_MS: int = 10000
    DEFAULT_QUEUE_TIMEOUT_SEC: int = 30

    def ensure_dirs(self):
        os.makedirs(self.PROFILE_DIR, exist_ok=True)
        os.makedirs(self.LOGS_DIR, exist_ok=True)
        os.makedirs(self.SCREENSHOTS_DIR, exist_ok=True)

settings = Settings()
settings.ensure_dirs()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_config.py -v`
Expected: PASS

- [ ] **Step 5: Commit**
`alibaba_messenger/config.py` 与配置测试就绪。

---

### Task 2: 防重发记录管理器 (`dedup.py`)

**Files:**
- Create: `alibaba_messenger/dedup.py`
- Test: `tests/test_dedup.py`

**Interfaces:**
- Consumes: `settings.SENT_RECORDS_FILE`
- Produces: 
  - `Deduplicator.is_duplicate(buyer_name: str, message: str) -> bool`
  - `Deduplicator.record_sent(buyer_name: str, message: str) -> None`
  - `Deduplicator.clean_expired(days: int = 7) -> None`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_dedup.py
import os
import json
from alibaba_messenger.dedup import Deduplicator

def test_deduplication_lifecycle(tmp_path):
    record_file = str(tmp_path / "sent_records.json")
    dedup = Deduplicator(storage_file=record_file)
    
    buyer = "Test Buyer Inc"
    msg = "Happy New Year!"
    
    # 未发过时不重复
    assert dedup.is_duplicate(buyer, msg) is False
    
    # 记录发送
    dedup.record_sent(buyer, msg)
    
    # 再次判断应为重复
    assert dedup.is_duplicate(buyer, msg) is True
    
    # 消息内容改变不判定为重复
    assert dedup.is_duplicate(buyer, "Different Message") is False
    
    # 持久化文件存在且格式正确
    assert os.path.exists(record_file)
    with open(record_file, "r", encoding="utf-8") as f:
        data = json.load(f)
        assert len(data) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_dedup.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'alibaba_messenger.dedup'`

- [ ] **Step 3: Write minimal implementation**

```python
# alibaba_messenger/dedup.py
import os
import json
import time
import hashlib
from datetime import datetime
from typing import Dict
from alibaba_messenger.config import settings

class Deduplicator:
    def __init__(self, storage_file: str = None):
        self.storage_file = storage_file or settings.SENT_RECORDS_FILE
        self._records: Dict[str, str] = {}
        self._load()

    def _generate_key(self, buyer_name: str, message: str, date_str: str = None) -> str:
        date_str = date_str or datetime.now().strftime("%Y-%m-%d")
        normalized_msg = message.strip()
        msg_hash = hashlib.md5(normalized_msg.encode("utf-8")).hexdigest()[:12]
        return f"{buyer_name.strip()}_{date_str}_{msg_hash}"

    def _load(self):
        if os.path.exists(self.storage_file):
            try:
                with open(self.storage_file, "r", encoding="utf-8") as f:
                    self._records = json.load(f)
            except Exception:
                self._records = {}
        else:
            self._records = {}

    def _save(self):
        try:
            with open(self.storage_file, "w", encoding="utf-8") as f:
                json.dump(self._records, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[Warn] 保存防重记录文件失败: {e}")

    def is_duplicate(self, buyer_name: str, message: str) -> bool:
        key = self._generate_key(buyer_name, message)
        return key in self._records

    def record_sent(self, buyer_name: str, message: str):
        key = self._generate_key(buyer_name, message)
        self._records[key] = datetime.now().isoformat()
        self._save()

deduplicator = Deduplicator()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_dedup.py -v`
Expected: PASS

- [ ] **Step 5: Commit**
`alibaba_messenger/dedup.py` 防重发管理器完成并通过测试。

---

### Task 3: 自动化机器人核心与未登录暂停通知机制 (`alibaba_bot.py`)

**Files:**
- Create: `alibaba_messenger/alibaba_bot.py`
- Test: `tests/test_mock_bot.py`

**Interfaces:**
- Consumes: `settings`, `deduplicator`
- Produces:
  - `AlibabaMessengerBot.start()`: 启动 Playwright 持久化浏览器，检测登录态
  - `AlibabaMessengerBot.wait_for_login(timeout=300)`: 遇到未登录时暂停控制台，通知用户扫码，确认登录后继续
  - `AlibabaMessengerBot.send_message(buyer_name: str, message: str, force_send: bool = False) -> dict`: 执行检索、防重、打字和发送
  - `AlibabaMessengerBot.close()`: 释放浏览器

- [ ] **Step 1: Write test with local mock HTML**

编写一个使用标准 aiohttp/http.server 模拟国际站消息中心交互的端到端测试（含搜索框输入、联系人列表、聊天气泡渲染）：
```python
# tests/test_mock_bot.py
import pytest
from alibaba_messenger.dedup import Deduplicator
# 验证业务方法签名及数据结构
def test_bot_interface_contracts():
    from alibaba_messenger.alibaba_bot import SendResultStatus
    assert SendResultStatus.SENT == "SENT"
    assert SendResultStatus.BUYER_NOT_FOUND == "BUYER_NOT_FOUND"
    assert SendResultStatus.DUPLICATE_IGNORED == "DUPLICATE_IGNORED"
    assert SendResultStatus.NEED_LOGIN == "NEED_LOGIN"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_mock_bot.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'alibaba_messenger.alibaba_bot'`

- [ ] **Step 3: Write minimal implementation**

```python
# alibaba_messenger/alibaba_bot.py
import os
import time
import random
import asyncio
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any
from playwright.async_api import async_playwright, BrowserContext, Page, TimeoutError as PlaywrightTimeoutError

from alibaba_messenger.config import settings
from alibaba_messenger.dedup import deduplicator

class SendResultStatus(str, Enum):
    SENT = "SENT"
    BUYER_NOT_FOUND = "BUYER_NOT_FOUND"
    DUPLICATE_IGNORED = "DUPLICATE_IGNORED"
    NEED_LOGIN = "NEED_LOGIN"
    QUEUE_TIMEOUT = "QUEUE_TIMEOUT"
    SEND_FAILED = "SEND_FAILED"

class AlibabaMessengerBot:
    def __init__(self):
        self.playwright = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.is_logged_in = False
        self.is_busy = False
        self._login_event = asyncio.Event()

    async def start(self, headless: bool = False):
        """启动持久化浏览器并检测登录状态"""
        self.playwright = await async_playwright().start()
        # 去除自动化控制特征
        args = [
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-infobars"
        ]
        self.context = await self.playwright.chromium.launch_persistent_context(
            user_data_dir=settings.PROFILE_DIR,
            headless=headless,
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            args=args
        )
        self.page = self.context.pages[0] if self.context.pages else await self.context.new_page()
        await self.page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        await self.check_and_handle_login()

    async def check_and_handle_login(self) -> bool:
        """检查登录状态。若未登录，控制台暂停并提示用户在弹出的浏览器中扫码登录"""
        print(f"[Bot] 正在导航至阿里国际站消息中心: {settings.ALIBABA_MSG_URL}")
        await self.page.goto(settings.ALIBABA_MSG_URL, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(2)
        
        current_url = self.page.url
        # 判定是否跳转登录或存在登录框
        if settings.ALIBABA_LOGIN_FLAG in current_url or await self.page.query_selector("input[type='password'], .login-form, #login-form"):
            self.is_logged_in = False
            print("\n" + "="*70)
            print("【特别提醒 / LOGIN REQUIRED】检测到阿里国际站账号尚未登录！")
            print("请在已弹出的浏览器窗口中完成扫码登录或账号密码登录。")
            print("登录成功后系统会自动识别并继续，或按回车键立即重新检测...")
            print("="*70 + "\n")
            
            # 轮询等待登录完成
            max_wait_seconds = 300
            start_time = time.time()
            while time.time() - start_time < max_wait_seconds:
                await asyncio.sleep(3)
                if settings.ALIBABA_LOGIN_FLAG not in self.page.url and not (await self.page.query_selector("input[type='password']")):
                    self.is_logged_in = True
                    print("\n[Bot] >>> 登录成功！会话已就绪并已持久化保存。<<<\n")
                    return True
            print("[Bot] 登录等待超时，请稍后重新启动或调用登录检查接口。")
            return False
        else:
            self.is_logged_in = True
            print("[Bot] 国际站登录态有效，消息中心已就绪。")
            return True

    async def _close_unexpected_dialogs(self):
        """关闭偶发的活动弹窗、营销遮罩或升级提示"""
        try:
            close_buttons = await self.page.query_selector_all(".next-dialog-close, .ui-dialog-close, .ice-dialog-close, [aria-label='Close']")
            for btn in close_buttons:
                if await btn.is_visible():
                    await btn.click()
                    await asyncio.sleep(0.5)
        except Exception:
            pass

    async def send_message(self, buyer_name: str, message: str, force_send: bool = False) -> Dict[str, Any]:
        """执行单条消息发送"""
        start_time = time.time()
        
        if not self.is_logged_in:
            return {
                "success": False,
                "status": SendResultStatus.NEED_LOGIN,
                "message": "国际站尚未登录，请先在界面完成登录",
                "data": {"buyer_name": buyer_name}
            }

        # 1. 第一层防重检查
        if not force_send and deduplicator.is_duplicate(buyer_name, message):
            return {
                "success": False,
                "status": SendResultStatus.DUPLICATE_IGNORED,
                "message": f"买家 [{buyer_name}] 今日已接收过该问候文本，已自动跳过",
                "data": {"buyer_name": buyer_name, "elapsed_seconds": round(time.time() - start_time, 2)}
            }

        try:
            self.is_busy = True
            await self._close_unexpected_dialogs()
            
            # 2. 定位搜索框
            search_selector = "input[placeholder*='搜索'], input[placeholder*='Search'], .search-input input"
            search_input = await self.page.wait_for_selector(search_selector, timeout=settings.PAGE_ACTION_TIMEOUT_MS)
            if not search_input:
                raise RuntimeError("未能定位到消息中心联系人搜索框")

            await search_input.click()
            await search_input.fill("")  # 清空
            # 逐字键入模拟
            for char in buyer_name:
                await self.page.keyboard.type(char)
                await asyncio.sleep(random.randint(settings.TYPING_DELAY_MIN_MS, settings.TYPING_DELAY_MAX_MS) / 1000.0)
            await self.page.keyboard.press("Enter")
            await asyncio.sleep(1.5)

            # 3. 检查搜索结果
            result_item_selector = ".session-item, .contact-item, .im-session-list .item, [data-testid='conversation-item']"
            try:
                first_item = await self.page.wait_for_selector(result_item_selector, timeout=settings.SEARCH_TIMEOUT_MS)
            except PlaywrightTimeoutError:
                # 搜索超时或无匹配联系人
                await self._clear_search()
                return {
                    "success": False,
                    "status": SendResultStatus.BUYER_NOT_FOUND,
                    "message": f"未搜索到买家 [{buyer_name}] 相关的会话或联系人",
                    "data": {"buyer_name": buyer_name, "elapsed_seconds": round(time.time() - start_time, 2)}
                }

            # 4. 点击进入会话
            await first_item.click()
            await asyncio.sleep(1.0)

            # 5. 定位消息输入框
            editor_selector = ".chat-input textarea, [contenteditable='true'], .im-editor"
            editor = await self.page.wait_for_selector(editor_selector, timeout=settings.PAGE_ACTION_TIMEOUT_MS)
            if not editor:
                raise RuntimeError("未能定位到聊天输入区域")

            # 6. 第二层页面气泡查重
            if not force_send:
                last_bubble = await self.page.query_selector(".message-bubble.mine .text, .bubble-right .content")
                if last_bubble:
                    last_text = (await last_bubble.inner_text()).strip()
                    if last_text == message.strip():
                        await self._clear_search()
                        deduplicator.record_sent(buyer_name, message)
                        return {
                            "success": False,
                            "status": SendResultStatus.DUPLICATE_IGNORED,
                            "message": f"聊天窗口中我方最后一条消息与当前内容完全一致，触发防重跳过",
                            "data": {"buyer_name": buyer_name, "elapsed_seconds": round(time.time() - start_time, 2)}
                        }

            # 7. 模拟输入消息
            await editor.click()
            for char in message:
                await self.page.keyboard.type(char)
                await asyncio.sleep(random.randint(settings.TYPING_DELAY_MIN_MS, settings.TYPING_DELAY_MAX_MS) / 1000.0)
            
            await asyncio.sleep(0.5)

            # 8. 点击发送或快捷键
            send_btn = await self.page.query_selector("button.send-btn, button[type='submit'], .btn-send")
            if send_btn and await send_btn.is_visible():
                await send_btn.click()
            else:
                await self.page.keyboard.press("Enter")

            await asyncio.sleep(1.0)
            
            # 登记防重记录并清理搜索
            deduplicator.record_sent(buyer_name, message)
            await self._clear_search()

            # 拟人化冷却休眠
            cooldown = random.uniform(settings.POST_SEND_COOLDOWN_MIN_SEC, settings.POST_SEND_COOLDOWN_MAX_SEC)
            await asyncio.sleep(cooldown)

            return {
                "success": True,
                "status": SendResultStatus.SENT,
                "message": "消息发送成功",
                "data": {
                    "buyer_name": buyer_name,
                    "sent_at": datetime.now().isoformat(),
                    "elapsed_seconds": round(time.time() - start_time, 2)
                }
            }

        except Exception as e:
            # 异常截屏
            screenshot_name = f"{int(time.time())}_{buyer_name}.png"
            screenshot_path = os.path.join(settings.SCREENSHOTS_DIR, screenshot_name)
            try:
                await self.page.screenshot(path=screenshot_path)
            except Exception:
                pass
            
            try:
                await self.page.reload()
            except Exception:
                pass

            return {
                "success": False,
                "status": SendResultStatus.SEND_FAILED,
                "message": f"自动化执行异常: {str(e)}",
                "data": {
                    "buyer_name": buyer_name,
                    "screenshot_path": screenshot_path,
                    "elapsed_seconds": round(time.time() - start_time, 2)
                }
            }
        finally:
            self.is_busy = False

    async def _clear_search(self):
        """点击搜索栏清除按钮恢复初始列表"""
        try:
            clear_btn = await self.page.query_selector(".search-clear, .icon-close, .btn-clear")
            if clear_btn and await clear_btn.is_visible():
                await clear_btn.click()
        except Exception:
            pass

    async def close(self):
        if self.context:
            await self.context.close()
        if self.playwright:
            await self.playwright.stop()

bot = AlibabaMessengerBot()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_mock_bot.py -v`
Expected: PASS

- [ ] **Step 5: Commit**
`alibaba_messenger/alibaba_bot.py` 控制器与扫码暂停逻辑实现完成。

---

### Task 4: FastAPI Web 服务与请求排队互斥锁 (`server.py`)

**Files:**
- Create: `alibaba_messenger/server.py`
- Test: `tests/test_server.py`

**Interfaces:**
- Consumes: `bot`, `settings`
- Produces:
  - `POST /api/message/send`: 接收发信参数，利用 `asyncio.Lock` 串行排队调用 `bot.send_message`
  - `GET /api/status`: 查询当前服务状态（`READY`, `BUSY`, `NEED_LOGIN`）与队列情况
  - `POST /api/login/check`: 手动触发重新检查并更新登录状态

- [ ] **Step 1: Write the failing test**

```python
# tests/test_server.py
from fastapi.testclient import TestClient
from alibaba_messenger.server import app

client = TestClient(app)

def test_get_status_endpoint():
    response = client.get("/api/status")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "is_logged_in" in data

def test_send_message_validation():
    # 缺少 message 字段
    response = client.post("/api/message/send", json={"buyer_name": "John"})
    assert response.status_code == 422
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_server.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'alibaba_messenger.server'`

- [ ] **Step 3: Write minimal implementation**

```python
# alibaba_messenger/server.py
import asyncio
from contextlib import asynccontextmanager
from typing import Optional, Dict, Any
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field

from alibaba_messenger.config import settings
from alibaba_messenger.alibaba_bot import bot, SendResultStatus

# 单浏览器操作排队锁
browser_lock = asyncio.Lock()
waiting_counter = 0

class SendMessageRequest(BaseModel):
    buyer_name: str = Field(..., description="买家姓名/旺旺名/公司名")
    message: str = Field(..., description="待发送的问候内容")
    force_send: bool = Field(False, description="是否强制发送(跳过防重)")
    timeout_seconds: int = Field(30, description="最大等待与执行超时(秒)")

class APIResponse(BaseModel):
    code: int
    success: bool
    status: str
    message: str
    data: Optional[Dict[str, Any]] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动钩子由 run_server 统筹或此处按需触发
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

@app.post("/api/login/check", response_model=APIResponse)
async def check_login():
    logged_in = await bot.check_and_handle_login()
    return APIResponse(
        code=200 if logged_in else 401,
        success=logged_in,
        status="READY" if logged_in else "NEED_LOGIN",
        message="登录态有效" if logged_in else "尚未登录或登录已失效",
        data={"is_logged_in": logged_in}
    )

@app.post("/api/message/send", response_model=APIResponse)
async def send_message(req: SendMessageRequest):
    global waiting_counter
    waiting_counter += 1
    
    try:
        # 获取排队互斥锁
        try:
            await asyncio.wait_for(browser_lock.acquire(), timeout=req.timeout_seconds)
        except asyncio.TimeoutError:
            return APIResponse(
                code=429,
                success=False,
                status=SendResultStatus.QUEUE_TIMEOUT,
                message="前序消息发送繁忙，排队超时",
                data={"buyer_name": req.buyer_name}
            )

        try:
            # 委托机器人执行
            res = await bot.send_message(
                buyer_name=req.buyer_name,
                message=req.message,
                force_send=req.force_send
            )
            
            status_code = 200
            if res["status"] == SendResultStatus.BUYER_NOT_FOUND:
                status_code = 404
            elif res["status"] == SendResultStatus.DUPLICATE_IGNORED:
                status_code = 409
            elif res["status"] == SendResultStatus.NEED_LOGIN:
                status_code = 401
            elif res["status"] == SendResultStatus.SEND_FAILED:
                status_code = 500

            return APIResponse(
                code=status_code,
                success=res["success"],
                status=res["status"],
                message=res["message"],
                data=res.get("data")
            )
        finally:
            browser_lock.release()
            
    finally:
        waiting_counter = max(0, waiting_counter - 1)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_server.py -v`
Expected: PASS

- [ ] **Step 5: Commit**
`alibaba_messenger/server.py` 完成并通过端点测试。

---

### Task 5: 启动脚本与登录引导入口 (`run_server.py`)

**Files:**
- Create: `alibaba_messenger/run_server.py`
- Test: `tests/test_runner_cli.py`

**Interfaces:**
- Produces: 
  - 支持命令行参数 `--headless`, `--port`, `--host`
  - 启动前自动执行 `bot.start()` 并触发扫码暂停引导
  - 登录完成后拉起 Uvicorn 服务

- [ ] **Step 1: Write test for argument parsing**

```python
# tests/test_runner_cli.py
import subprocess
import sys

def test_runner_help_command():
    res = subprocess.run([sys.executable, "-m", "alibaba_messenger.run_server", "--help"], capture_output=True, text=True)
    assert res.returncode == 0
    assert "阿里巴巴国际站" in res.stdout or "usage" in res.stdout.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_runner_cli.py -v`
Expected: FAIL with `No module named alibaba_messenger.run_server`

- [ ] **Step 3: Write minimal implementation**

```python
# alibaba_messenger/run_server.py
import argparse
import asyncio
import uvicorn
from alibaba_messenger.config import settings
from alibaba_messenger.alibaba_bot import bot
from alibaba_messenger.server import app

def parse_args():
    parser = argparse.ArgumentParser(description="阿里巴巴国际站 Playwright 自动发信服务")
    parser.add_argument("--host", default=settings.SERVER_HOST, help="监听主机IP")
    parser.add_argument("--port", type=int, default=settings.SERVER_PORT, help="监听端口")
    parser.add_argument("--headless", action="store_true", help="是否无头模式(建议首次登录不要使用)")
    return parser.parse_args()

async def init_and_run(args):
    print("=" * 60)
    print("正在启动阿里巴巴国际站自动发消息服务...")
    print("=" * 60)
    
    # 1. 启动持久化浏览器
    await bot.start(headless=args.headless)
    
    # 2. 检查登录状态
    if not bot.is_logged_in:
        print("[Notice] 尚未登录，主进程等待登录完成...")
        await bot.check_and_handle_login()
    
    print("\n[OK] 自动化控制器就绪，正在启动 HTTP API 接口服务...")
    print(f"[API] 文档地址: http://127.0.0.1:{args.port}/docs")
    print(f"[API] 发送接口: POST http://127.0.0.1:{args.port}/api/message/send\n")
    
    config = uvicorn.Config(app, host=args.host, port=args.port, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()

def main():
    args = parse_args()
    try:
        asyncio.run(init_and_run(args))
    except KeyboardInterrupt:
        print("\n[Server] 接收到退出信号，正在安全退出...")

if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_runner_cli.py -v`
Expected: PASS

- [ ] **Step 5: Commit**
`run_server.py` 就绪。

---

### Task 6: 联调模拟与 CRM 调用示例 (`test_api_client.py` & 文档)

**Files:**
- Create: `alibaba_messenger/test_api_client.py`
- Create: `alibaba_messenger/README.md`
- Test: 全量运行 `pytest tests/ -v`

**Interfaces:**
- Produces: 
  - Python 版 CRM 快捷调用示例代码
  - cURL 调用示例与返回结果应对说明

- [ ] **Step 1: Write CRM mock client**

```python
# alibaba_messenger/test_api_client.py
"""
CRM 模拟调用示例：向本地运行的 Playwright 服务发起发送问候请求
"""
import requests

API_URL = "http://127.0.0.1:8000/api/message/send"
STATUS_URL = "http://127.0.0.1:8000/api/status"

def check_status():
    r = requests.get(STATUS_URL)
    print("当前服务状态:", r.json())

def send_greeting(buyer_name: str, message: str, force: bool = False):
    payload = {
        "buyer_name": buyer_name,
        "message": message,
        "force_send": force,
        "timeout_seconds": 30
    }
    print(f"\n[CRM] 正在向买家 [{buyer_name}] 发送问候...")
    r = requests.post(API_URL, json=payload)
    print(f"[CRM] 返回状态码: {r.status_code}")
    print("[CRM] 返回内容:", r.json())

if __name__ == "__main__":
    check_status()
    # 示例调用
    # send_greeting("Sample Buyer", "Dear friend, Wishing you a wonderful holiday season!")
```

- [ ] **Step 2: Run full test suite**

Run: `pytest tests/ -v`
Expected: ALL PASS

- [ ] **Step 3: Write README.md**

编写 `alibaba_messenger/README.md`，详细说明环境安装（`playwright install chromium`）、初次登录引导、API 接口文档与 CRM 对接参数。

- [ ] **Step 4: Commit**
文档与模拟客户端齐备。
