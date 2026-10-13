# -*- coding: utf-8 -*-
import os
import time
import random
import re
import asyncio
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List
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
        self.recovery_login_handler = None
        self._inquiry_countries: Dict[str, str] = {}
        self._last_refresh_time: float = time.time()
        self._last_keep_alive: float = time.time()

    def get_last_extracted_country(self, inquiry_id: str) -> str:
        """获取指定商机缓存的买家国家/地区"""
        return self._inquiry_countries.get(str(inquiry_id or "").strip(), "")

    async def keep_alive(self, force_reload: bool = False, max_idle_seconds: float = 180.0) -> bool:
        """保持浏览器活跃与会话连接，定时刷新商机沟通列表以获取最新数据并自动关闭弹窗"""
        now = time.time()
        self._last_keep_alive = now

        if not self.page or self.page.is_closed():
            self.is_logged_in = False
            return False

        try:
            curr_url = self.page.url or ""
            if settings.ALIBABA_LOGIN_FLAG in curr_url:
                self.is_logged_in = False
                return False

            # 关闭可能出现的阻挡弹窗
            await self._close_unexpected_dialogs()

            idle_duration = now - self._last_refresh_time
            if force_reload or idle_duration >= max_idle_seconds:
                # 刷新页面以拉取最新商机会话与长连接消息
                try:
                    await self.page.reload(wait_until="domcontentloaded", timeout=30000)
                    try:
                        await self.page.wait_for_load_state("load", timeout=5000)
                    except Exception:
                        pass
                    await asyncio.sleep(1.5)
                except Exception as reload_err:
                    print(f"[Bot] keep_alive 页面刷新异常: {reload_err}")

                # 刷新后再次校验是否掉登
                curr_url = self.page.url or ""
                if settings.ALIBABA_LOGIN_FLAG in curr_url:
                    self.is_logged_in = False
                    return False

                await self._close_unexpected_dialogs()
                self._last_refresh_time = time.time()

            return self.is_logged_in
        except Exception as e:
            print(f"[Bot] keep_alive 异常: {e}")
            return False

    async def start(self, headless: bool = False):
        """启动持久化浏览器并检测登录状态"""
        self.playwright = await async_playwright().start()
        # 去除自动化控制特征
        args = [
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-infobars"
        ]
        try:
            self.context = await self.playwright.chromium.launch_persistent_context(
                user_data_dir=settings.PROFILE_DIR,
                headless=headless,
                viewport={"width": 1280, "height": 800},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                args=args
            )
        except Exception as exc:
            await self.playwright.stop()
            raise RuntimeError(
                "Alibaba browser profile is already in use. "
                f"Close all Chrome/Worker windows using {settings.PROFILE_DIR}, then retry."
            ) from exc
        self.page = self.context.pages[0] if self.context.pages else await self.context.new_page()
        await self.page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        await self.check_and_handle_login()

    async def check_and_handle_login(self) -> bool:
        """检查登录状态。若未登录，控制台暂停并提示用户在弹出的浏览器中扫码登录"""
        if not self.page:
            return False
            
        print(f"[Bot] 正在导航至阿里国际站消息中心: {settings.ALIBABA_MSG_URL}")
        try:
            await self.page.goto(settings.ALIBABA_MSG_URL, wait_until="domcontentloaded", timeout=30000)
            try:
                await self.page.wait_for_load_state("load", timeout=5000)
            except Exception:
                pass
            await asyncio.sleep(2)
        except Exception as e:
            print(f"[Bot] 页面导航异常: {e}")

        # 容错获取密码框与登录特征，防止偶发页面二次重定向销毁执行上下文
        has_pwd = False
        try:
            has_pwd = bool(await self.page.query_selector("input[type='password'], .login-form, #login-form"))
        except Exception:
            await asyncio.sleep(2)
            try:
                has_pwd = bool(await self.page.query_selector("input[type='password'], .login-form, #login-form"))
            except Exception:
                has_pwd = False

        current_url = self.page.url
        is_login_page = settings.ALIBABA_LOGIN_FLAG in current_url or has_pwd
        
        if is_login_page:
            self.is_logged_in = False
            print("\n" + "="*70)
            print("【特别提醒 / LOGIN REQUIRED】检测到阿里国际站账号尚未登录！")
            print("请在已弹出的浏览器窗口中完成扫码登录或账号密码登录。")
            print("登录成功后系统会自动识别并继续，或在终端查看状态...")
            print("="*70 + "\n")
            
            # 轮询等待登录完成（最长等待 300 秒）
            max_wait_seconds = 300
            start_time = time.time()
            while time.time() - start_time < max_wait_seconds:
                await asyncio.sleep(3)
                if self.recovery_login_handler is not None:
                    await self.recovery_login_handler(self.page)
                try:
                    current_url = self.page.url
                    has_pwd = bool(await self.page.query_selector("input[type='password']"))
                    if settings.ALIBABA_LOGIN_FLAG not in current_url and not has_pwd:
                        self.is_logged_in = True
                        print("\n[Bot] >>> 登录成功！会话已就绪并已持久化保存。<<<\n")
                        return True
                except Exception:
                    pass
            print("[Bot] 登录等待超时，请稍后重新启动或调用登录检查接口。")
            return False
        else:
            self.is_logged_in = True
            print("[Bot] 国际站登录态有效，消息中心已就绪。")
            return True

    async def _close_unexpected_dialogs(self, page=None):
        """关闭偶发的活动弹窗、营销遮罩或升级提示"""
        target = page or self.page
        if not target:
            return
        try:
            close_buttons = await target.query_selector_all(".next-dialog-close, .ui-dialog-close, .ice-dialog-close, .next-feedback-close, [aria-label='Close'], span.next-icon-close")
            for btn in close_buttons:
                if await btn.is_visible():
                    await btn.click()
                    await asyncio.sleep(0.3)
        except Exception:
            pass

    async def _get_current_page_number(self) -> int:
        """获取商机沟通列表当前所处的激活页码"""
        if not self.page:
            return 1
        try:
            val = await self.page.evaluate("""
            () => {
                const cur = document.querySelector(".next-pagination-item.next-current, .next-pagination-item.active, [aria-current='page'], .ui2-pagination-current");
                if (cur && cur.innerText) {
                    const num = parseInt(cur.innerText.trim(), 10);
                    if (!isNaN(num) && num > 0) return num;
                }
                return 1;
            }
            """)
            if isinstance(val, (int, float)):
                return int(val)
            if isinstance(val, str) and val.strip().isdigit():
                return int(val.strip())
            return 1
        except Exception:
            return 1

    async def _find_inquiry_row(
        self,
        buyer_name: Optional[str] = None,
        inquiry_id: Optional[str] = None,
        max_pages: int = 5
    ) -> tuple[Optional[Dict[str, Any]], int]:
        """在商机沟通列表中查找指定买家或询价单号，支持智能跨页切换"""
        if not self.page:
            return None, 1

        script = """
        (args) => {
            const targetBuyer = (args.buyer || "").trim().toLowerCase();
            const targetId = (args.inquiryId || "").trim();

            const detailLinks = Array.from(document.querySelectorAll("a, button, span")).filter(el => {
                return el.innerText && el.innerText.trim() === "查看详情";
            });
            for (let i = 0; i < detailLinks.length; i++) {
                const link = detailLinks[i];
                let cur = link;
                let row = null;
                while (cur && cur !== document.body) {
                    if (cur.innerText && cur.innerText.includes("询价单号")) {
                        row = cur;
                        if (cur.parentElement && (cur.parentElement.innerText.match(/询价单号/g) || []).length > 1) break;
                    }
                    cur = cur.parentElement;
                }
                if (!row) continue;

                const text = row.innerText || "";
                const idMatch = text.match(/询价单号[:：\\s]*(\\d+)/) || text.match(/Inquiry ID[:：\\s]*(\\d+)/i);
                const idNum = idMatch ? idMatch[1] : "";

                // 提取买家姓名
                let name = "";
                const avatars = Array.from(row.querySelectorAll("[class*='avatar'], [class*='Avatar'], [class*='initials']"));
                if (avatars.length > 0) {
                    const avatar = avatars[0];
                    const container = avatar.closest("div, td, [class*='customer'], [class*='buyer']") || avatar.parentElement;
                    const candidates = Array.from(container.querySelectorAll("a, span, div, p"))
                        .map(e => e.innerText.trim())
                        .filter(t => t && t.length >= 2 && t.length <= 40 &&
                                     !t.toLowerCase().includes("inquiry") &&
                                     !t.includes("TM 商机") && !t.includes("洽谈中") &&
                                     !t.includes("待回复") && !t.includes("User name") &&
                                     !t.match(/^L\\d\\+?$/i) && !t.includes("查看详情"));
                    if (candidates.length > 0) name = candidates[0];
                }
                if (!name) {
                    const nameEl = row.querySelector(".aui2-grid-name, [class*='buyer-name'], [class*='customer-name']");
                    if (nameEl && nameEl.innerText.trim()) name = nameEl.innerText.trim();
                }
                if (!name) {
                    const allLeafElements = Array.from(row.querySelectorAll("*")).filter(el => el.children.length === 0);
                    for (const el of allLeafElements) {
                        const t = el.innerText ? el.innerText.trim() : "";
                        if (!t || t.length < 2 || t.length > 40) continue;
                        const lower = t.toLowerCase();
                        if (lower.includes("inquiry") || lower.includes("商机") || lower.includes("洽谈") ||
                            lower.includes("待回复") || lower.includes("已下单") || lower.includes("询价") ||
                            lower.includes("时间") || lower.includes("user name") || lower.includes("详情") ||
                            t.match(/^L\\d\\+?$/i) || t.match(/^\\d+$/)) continue;
                        name = t;
                        break;
                    }
                }

                // 提取最新消息片段
                let snippet = "";
                const msgEl = row.querySelector(".buyer-chat-msg, [class*='message'], [class*='chat']");
                if (msgEl && msgEl.innerText.trim()) {
                    snippet = msgEl.innerText.trim();
                }
                if (!snippet) {
                    const lines = text.split("\\n").map(s => s.trim()).filter(Boolean);
                    for (const line of lines) {
                        if (line.toLowerCase().includes("inquiry from tm")) {
                            const clean = line.replace(/.*inquiry from tm[:：\\s]*/i, "").trim();
                            if (clean && clean !== "In...") { snippet = clean; break; }
                        } else if (line !== name && line.length > 5 &&
                                   !line.includes("询价单号") && !line.includes("时间") &&
                                   !line.includes("洽谈中") && !line.includes("TM 商机") &&
                                   !line.includes("User name") && !line.includes("查看详情")) {
                            snippet = line;
                            break;
                        }
                    }
                }

                const updateMatch = text.match(/更新时间[:：\\s]*([^\\s\\n]+)/);

                // 提取买家国家/地区
                let country = "";
                const flagCandidates = Array.from(row.querySelectorAll(
                    "img[src*='flag'], img[src*='country'], img[src*='nation'], " +
                    "[class*='flag'], [class*='country'], [class*='nation'], " +
                    "[data-country], [data-country-code], [data-code]"
                ));
                for (const el of flagCandidates) {
                    const cls = (el.className || "").toString().toLowerCase();
                    const src = (el.getAttribute("src") || "").toLowerCase();
                    if (cls.includes("avatar") || src.includes("avatar") || cls.includes("logo") || src.includes("product")) {
                        continue;
                    }
                    const dataCode = el.getAttribute("data-country-code") || el.getAttribute("data-country") || el.getAttribute("data-code");
                    if (dataCode && dataCode.trim().length >= 2 && dataCode.trim().length <= 40) {
                        country = dataCode.trim();
                        break;
                    }
                    const titleVal = (el.getAttribute("title") || el.getAttribute("alt") || el.getAttribute("aria-label") || "").trim();
                    const titleLower = titleVal.toLowerCase();
                    if (titleVal && !titleLower.includes("avatar") && !titleLower.includes("logo") && !titleLower.includes("icon") && !titleLower.includes("image")) {
                        country = titleVal;
                        break;
                    }
                    const srcMatch = src.match(/\\/([a-z]{2})\\.(png|jpg|svg|webp|gif)/i);
                    if (srcMatch) {
                        country = srcMatch[1].toUpperCase();
                        break;
                    }
                    const classMatch = cls.match(/(?:flag|nation|country|fi)[-_]([a-z]{2})\b/i);
                    if (classMatch) {
                        country = classMatch[1].toUpperCase();
                        break;
                    }
                    const inner = el.innerText ? el.innerText.trim() : "";
                    if (inner && inner.length >= 2 && inner.length <= 40 && !inner.toLowerCase().includes("inquiry")) {
                        country = inner;
                        break;
                    }
                }
                if (!country) {
                    const countryMatch = text.match(/(?:国家\\/地区|国家|地区|Country\\/Region|Country|Region)[:：\\s]*([a-zA-Z\\u4e00-\\u9fa5\\s]{2,40})/i);
                    if (countryMatch) {
                        country = countryMatch[1].trim();
                    }
                }

                let match = false;
                if (targetId && idNum === targetId) {
                    match = true;
                } else if (targetBuyer) {
                    const lowerN = name.toLowerCase();
                    const lowerText = text.toLowerCase();
                    if (lowerN.includes(targetBuyer) || targetBuyer.includes(lowerN) || lowerText.includes(targetBuyer)) {
                        match = true;
                    }
                }

                if (match) {
                    return {
                        found: true,
                        index: i,
                        buyer_name: name || targetBuyer || "Unknown Buyer",
                        inquiry_id: idNum || targetId || "",
                        country: country,
                        last_message: snippet,
                        last_time: updateMatch ? updateMatch[1] : "",
                        href: link.getAttribute("href") || "",
                        target: link.getAttribute("target") || ""
                    };
                }
            }
            return { found: false };
        }
        """

        # 1. 先快速检查当前所在页
        curr_page = 1
        try:
            curr_page = await self._get_current_page_number()
            res = await self.page.evaluate(script, {"buyer": buyer_name or "", "inquiryId": inquiry_id or ""})
            if isinstance(res, dict) and res.get("found"):
                matched_inq = str(res.get("inquiry_id") or inquiry_id or "").strip()
                extracted_c = str(res.get("country") or "").strip()
                if matched_inq and extracted_c:
                    self._inquiry_countries[matched_inq] = extracted_c
                return res, curr_page
        except Exception:
            pass

        # 2. 跨页检索 (使用多策略翻页导航)
        for page_num in range(1, max_pages + 1):
            if page_num != curr_page:
                nav_ok = await self._navigate_conversation_page(page_num)
                if not nav_ok:
                    break
                curr_page = page_num
            try:
                res = await self.page.evaluate(script, {"buyer": buyer_name or "", "inquiryId": inquiry_id or ""})
                if isinstance(res, dict) and res.get("found"):
                    matched_inq = str(res.get("inquiry_id") or inquiry_id or "").strip()
                    extracted_c = str(res.get("country") or "").strip()
                    if matched_inq and extracted_c:
                        self._inquiry_countries[matched_inq] = extracted_c
                    return res, page_num
            except Exception:
                continue

        return None, 1

    async def send_message(
        self,
        buyer_name: str,
        message: str,
        inquiry_id: Optional[str] = None,
        force_send: bool = False,
        before_send=None,
    ) -> Dict[str, Any]:
        """向指定买家或商机单号发送消息，具备双层防重与拟人化延时"""
        start_time = time.time()
        
        if not self.is_logged_in:
            return {
                "success": False,
                "status": SendResultStatus.NEED_LOGIN,
                "message": "国际站尚未登录，请先在界面完成登录",
                "data": {"buyer_name": buyer_name, "inquiry_id": inquiry_id or ""}
            }

        # 1. 第一层防重检查
        effective_buyer = buyer_name or inquiry_id or "unknown"
        if not force_send and deduplicator.is_duplicate(effective_buyer, message):
            return {
                "success": False,
                "status": SendResultStatus.DUPLICATE_IGNORED,
                "message": f"买家 [{effective_buyer}] 今日已接收过该问候文本，已自动跳过",
                "data": {"buyer_name": effective_buyer, "inquiry_id": inquiry_id or "", "elapsed_seconds": round(time.time() - start_time, 2)}
            }

        target_page = None
        close_target_page = False
        try:
            self.is_busy = True
            await self._close_unexpected_dialogs()
            
            # 2. 在商机沟通列表中跨页定位买家/询盘单号
            table_row_btn, found_page = await self._find_inquiry_row(buyer_name=buyer_name, inquiry_id=inquiry_id)

            if not table_row_btn or not table_row_btn.get("found"):
                target_desc = f"买家 [{buyer_name}]" if buyer_name else f"商机ID [{inquiry_id}]"
                return {
                    "success": False,
                    "status": SendResultStatus.BUYER_NOT_FOUND,
                    "message": f"未在商机列表中找到{target_desc}",
                    "data": {"buyer_name": buyer_name, "inquiry_id": inquiry_id or "", "elapsed_seconds": round(time.time() - start_time, 2)}
                }

            real_buyer_name = table_row_btn.get("buyer_name") or buyer_name
            matched_id = table_row_btn.get("inquiry_id") or inquiry_id
            if before_send and (not inquiry_id or str(matched_id) != str(inquiry_id)):
                raise RuntimeError("Scheduled reply target was not confirmed")
            idx = table_row_btn.get("index", 0)

            # 打开商机详情页（点击当前行的“查看详情”）
            detail_links = await self.page.query_selector_all("a.actions-view-detail, .actions-view-detail")
            btn = None
            if idx < len(detail_links):
                btn = detail_links[idx]
            else:
                detail_locators = await self.page.locator("a, button, span").filter(has_text="查看详情").all()
                if idx < len(detail_locators):
                    btn = detail_locators[idx]

            if btn:
                if self.context:
                    try:
                        async with self.context.expect_page(timeout=5000) as new_page_info:
                            await btn.click()
                        target_page = await new_page_info.value
                        close_target_page = True
                        await target_page.wait_for_load_state("domcontentloaded")
                        await asyncio.sleep(2.0)
                    except Exception:
                        href = table_row_btn.get("href")
                        if href:
                            full_url = href if href.startswith("http") else (f"https:{href}" if href.startswith("//") else f"https://message.alibaba.com{href}")
                            target_page = await self.context.new_page()
                            close_target_page = True
                            await target_page.goto(full_url, wait_until="domcontentloaded", timeout=15000)
                            await asyncio.sleep(2.0)
                        else:
                            target_page = self.page
                else:
                    await btn.click()
                    target_page = self.page
                    await asyncio.sleep(2.0)
            else:
                target_page = self.page

            # 3. 定位并唤醒消息输入区域
            # 3.1 兼容 maDetail 详情页的两阶段模式（点击 .holder / .mock-reply 展开 TinyMCE 富文本输入框）
            holder = await target_page.query_selector(".holder, .mock-reply")
            if holder and await holder.is_visible():
                await holder.click()
                await asyncio.sleep(1.2)

            # 3.2 检查是否为 TinyMCE iframe (#normal-im-send_ifr)
            tinymce_body = target_page.frame_locator("#normal-im-send_ifr").locator("body")
            is_tinymce = False
            try:
                await tinymce_body.wait_for(timeout=4000)
                is_tinymce = True
            except Exception:
                is_tinymce = False

            # 4. 第二层页面气泡查重
            if not force_send:
                last_bubble = await target_page.query_selector(".message-bubble.mine .text, .bubble-right .content, [class*='supplier-content']")
                if last_bubble:
                    last_text = (await last_bubble.inner_text()).strip()
                    if last_text == message.strip():
                        await self._clear_search()
                        deduplicator.record_sent(real_buyer_name, message)
                        if close_target_page and target_page != self.page:
                            await target_page.close()
                        return {
                            "success": False,
                            "status": SendResultStatus.DUPLICATE_IGNORED,
                            "message": f"聊天窗口中我方最后一条消息与当前内容完全一致，触发防重跳过",
                            "data": {"buyer_name": real_buyer_name, "inquiry_id": matched_id or "", "elapsed_seconds": round(time.time() - start_time, 2)}
                        }

            # 5. 拟人化模拟输入消息
            if is_tinymce:
                # 强行聚焦 TinyMCE 编辑区域并清空既有内容/草稿
                await tinymce_body.click(force=True)
                await asyncio.sleep(0.3)
                try:
                    await tinymce_body.evaluate("el => { el.innerHTML = ''; el.innerText = ''; }")
                except Exception:
                    pass
                await target_page.keyboard.press("Control+A")
                await target_page.keyboard.press("Backspace")
                await asyncio.sleep(0.2)
                for char in message:
                    await target_page.keyboard.type(char)
                    await asyncio.sleep(random.randint(settings.TYPING_DELAY_MIN_MS, settings.TYPING_DELAY_MAX_MS) / 1000.0)
            else:
                editor_selector = "textarea:not([readonly]):not([aria-hidden='true']), [contenteditable='true']:not([aria-hidden='true']), input[placeholder*='输入']:not([readonly]), textarea, .chat-input textarea, .im-editor"
                editor = await target_page.wait_for_selector(editor_selector, timeout=settings.PAGE_ACTION_TIMEOUT_MS)
                if not editor:
                    raise RuntimeError("未能定位到聊天/回复输入区域")
                await editor.click()
                try:
                    await editor.evaluate("el => { if(el.value !== undefined) el.value = ''; else el.innerText = ''; }")
                except Exception:
                    pass
                await target_page.keyboard.press("Control+A")
                await target_page.keyboard.press("Backspace")
                for char in message:
                    await target_page.keyboard.type(char)
                    await asyncio.sleep(random.randint(settings.TYPING_DELAY_MIN_MS, settings.TYPING_DELAY_MAX_MS) / 1000.0)

            await asyncio.sleep(1.0)

            # 关闭可能浮现的提示浮层
            await self._close_unexpected_dialogs(target_page)

            # 6. 点击“发送”按钮
            send_btn = await target_page.query_selector("div.send[data-clk='send'], div[data-clk='send'], .send[data-clk='send']")
            if not send_btn:
                send_btn = await target_page.query_selector("button:has-text('发送'):not(.send-mock)")

            if before_send:
                if not send_btn or not await send_btn.is_visible():
                    raise RuntimeError("Scheduled reply send control was not confirmed")
                # Recheck CRM ownership and China-local hours immediately before dispatch.
                await send_btn.scroll_into_view_if_needed()
                await before_send()
                await send_btn.click()
            elif send_btn and await send_btn.is_visible():
                try:
                    await send_btn.scroll_into_view_if_needed()
                    await asyncio.sleep(0.3)
                    await send_btn.click()
                except Exception:
                    await send_btn.click(force=True)
            else:
                await target_page.keyboard.press("Enter")

            await asyncio.sleep(3.5)
            if before_send:
                bubbles = await target_page.locator(".message-bubble.mine .text, .bubble-right .content, [class*=supplier-content]").all_text_contents()
                normalized = " ".join(message.split())
                if not any(" ".join(text.split()) == normalized for text in bubbles):
                    raise RuntimeError("Scheduled reply delivery unconfirmed; do not retry automatically")

            # 发送后截取页面存照留证
            screenshot_path = ""
            try:
                screenshot_path = os.path.join(settings.SCREENSHOTS_DIR, f"sent_{matched_id or 'buyer'}_{int(time.time())}.png")
                await target_page.screenshot(path=screenshot_path)
            except Exception:
                pass

            # 登记防重记录并清理搜索
            deduplicator.record_sent(real_buyer_name, message)
            await self._clear_search()

            # 关闭详情新标签页（若打开了独立页面）
            if close_target_page and target_page != self.page:
                try:
                    await target_page.close()
                except Exception:
                    pass

            # 拟人化冷却休眠
            cooldown = random.uniform(settings.POST_SEND_COOLDOWN_MIN_SEC, settings.POST_SEND_COOLDOWN_MAX_SEC)
            await asyncio.sleep(cooldown)

            return {
                "success": True,
                "status": SendResultStatus.SENT,
                "message": f"成功向买家 [{real_buyer_name}] 发送消息",
                "data": {
                    "buyer_name": real_buyer_name,
                    "inquiry_id": matched_id or "",
                    "message": message,
                    "sent_at": datetime.now().isoformat(),
                    "screenshot": screenshot_path,
                    "elapsed_seconds": round(time.time() - start_time, 2)
                }
            }

        except Exception as e:
            # 异常截屏：若详情页仍存在则优先截取详情页
            screenshot_name = f"{int(time.time())}_{buyer_name}.png"
            screenshot_path = os.path.join(settings.SCREENSHOTS_DIR, screenshot_name)
            shot_page = target_page if (target_page and not target_page.is_closed()) else self.page
            try:
                if shot_page:
                    await shot_page.screenshot(path=screenshot_path)
            except Exception:
                pass
            
            if close_target_page and target_page and not target_page.is_closed() and target_page != self.page:
                try:
                    await target_page.close()
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

    async def get_recent_conversations(self, limit: int = 20, auto_refresh: bool = False) -> Dict[str, Any]:
        """获取最近会话列表及未读状态。若 auto_refresh=True，则先执行页面保活刷新"""
        if auto_refresh:
            await self.keep_alive(force_reload=True)

        if not self.is_logged_in:
            return {
                "success": False,
                "status": SendResultStatus.NEED_LOGIN,
                "message": "国际站尚未登录，请先在界面完成登录",
                "data": {"conversations": []}
            }

        start_time = time.time()
        self.is_busy = True
        try:
            await self._close_unexpected_dialogs()
            
            # 优先方式：检测并解析阿里巴巴国际站「商机沟通 / 询价单管理」表格行
            inquiry_extract_script = """
            () => {
                const list = [];
                // 定位所有“查看详情”按钮/链接，其容器即为单条商机卡片/行
                const detailLinks = Array.from(document.querySelectorAll("a, button, span")).filter(el => {
                    return el.innerText && el.innerText.trim() === "查看详情";
                });
                
                for (const link of detailLinks) {
                    let cur = link;
                    let row = null;
                    while (cur && cur !== document.body) {
                        if (cur.innerText && cur.innerText.includes("询价单号")) {
                            row = cur;
                            if (cur.parentElement && (cur.parentElement.innerText.match(/询价单号/g) || []).length > 1) {
                                break;
                            }
                        }
                        cur = cur.parentElement;
                    }
                    if (!row) continue;

                    const text = row.innerText || "";
                    const idMatch = text.match(/询价单号[:：\\s]*(\\d+)/);
                    const inquiryId = idMatch ? idMatch[1] : "";

                    const updateMatch = text.match(/更新时间[:：\\s]*([^\\s\\n]+)/);
                    const createMatch = text.match(/创建时间[:：\\s]*([^\\s\\n]+)/);

                    // 1. 精确提取买家真实姓名 (Buyer Name)
                    // 逻辑：
                    // - 排除系统关键词：Inquiry from TM, TM 商机, 洽谈中, 待回复, 已下单, 询价单号, 时间, User name, 查看详情, L1+, L2+
                    // - 优先寻找头像容器附近的候选姓名
                    let buyerName = "";
                    const avatars = Array.from(row.querySelectorAll("[class*='avatar'], [class*='Avatar'], [class*='initials']"));
                    if (avatars.length > 0) {
                        const avatar = avatars[0];
                        const container = avatar.closest("div, td, [class*='customer'], [class*='buyer']") || avatar.parentElement;
                        const candidates = Array.from(container.querySelectorAll("a, span, div, p"))
                            .map(e => e.innerText.trim())
                            .filter(t => t && t.length >= 2 && t.length <= 40 &&
                                         !t.toLowerCase().includes("inquiry") &&
                                         !t.includes("TM 商机") && !t.includes("洽谈中") &&
                                         !t.includes("待回复") && !t.includes("User name") &&
                                         !t.match(/^L\\d\\+?$/i) && !t.includes("查看详情"));
                        if (candidates.length > 0) {
                            buyerName = candidates[0];
                        }
                    }

                    // 备选遍历行内所有纯文本叶子节点定位买家姓名
                    if (!buyerName) {
                        const allLeafElements = Array.from(row.querySelectorAll("*")).filter(el => el.children.length === 0);
                        for (const el of allLeafElements) {
                            const t = el.innerText ? el.innerText.trim() : "";
                            if (!t || t.length < 2 || t.length > 40) continue;
                            const lower = t.toLowerCase();
                            if (lower.includes("inquiry") || lower.includes("商机") || lower.includes("洽谈") ||
                                lower.includes("待回复") || lower.includes("已下单") || lower.includes("询价") ||
                                lower.includes("时间") || lower.includes("user name") || lower.includes("详情") ||
                                t.match(/^L\\d\\+?$/i) || t.match(/^\\d+$/)) {
                                continue;
                            }
                            buyerName = t;
                            break;
                        }
                    }

                    // 2. 提取国家/地区
                    let country = "";
                    const flagCandidates = Array.from(row.querySelectorAll(
                        "img[src*='flag'], img[src*='country'], img[src*='nation'], " +
                        "[class*='flag'], [class*='country'], [class*='nation'], " +
                        "[data-country], [data-country-code], [data-code]"
                    ));
                    for (const el of flagCandidates) {
                        const cls = (el.className || "").toString().toLowerCase();
                        const src = (el.getAttribute("src") || "").toLowerCase();
                        if (cls.includes("avatar") || src.includes("avatar") || cls.includes("logo") || src.includes("product")) {
                            continue;
                        }
                        const dataCode = el.getAttribute("data-country-code") || el.getAttribute("data-country") || el.getAttribute("data-code");
                        if (dataCode && dataCode.trim().length >= 2 && dataCode.trim().length <= 40) {
                            country = dataCode.trim();
                            break;
                        }
                        const titleVal = (el.getAttribute("title") || el.getAttribute("alt") || el.getAttribute("aria-label") || "").trim();
                        const titleLower = titleVal.toLowerCase();
                        if (titleVal && !titleLower.includes("avatar") && !titleLower.includes("logo") && !titleLower.includes("icon") && !titleLower.includes("image")) {
                            country = titleVal;
                            break;
                        }
                        const srcMatch = src.match(/\\/([a-z]{2})\\.(png|jpg|svg|webp|gif)/i);
                        if (srcMatch) {
                            country = srcMatch[1].toUpperCase();
                            break;
                        }
                        const classMatch = cls.match(/(?:flag|nation|country|fi)[-_]([a-z]{2})\b/i);
                        if (classMatch) {
                            country = classMatch[1].toUpperCase();
                            break;
                        }
                        const inner = el.innerText ? el.innerText.trim() : "";
                        if (inner && inner.length >= 2 && inner.length <= 40 && !inner.toLowerCase().includes("inquiry")) {
                            country = inner;
                            break;
                        }
                    }
                    if (!country) {
                        const countryMatch = text.match(/(?:国家\\/地区|国家|地区|Country\\/Region|Country|Region)[:：\\s]*([a-zA-Z\\u4e00-\\u9fa5\\s]{2,40})/i);
                        if (countryMatch) {
                            country = countryMatch[1].trim();
                        }
                    }

                    // 3. 提取消息内容摘要 (过滤掉 Inquiry from TM 等通用主题)
                    let lastMessage = "";
                    const lines = text.split("\\n").map(s => s.trim()).filter(Boolean);
                    for (const line of lines) {
                        if (line.toLowerCase().includes("inquiry from tm")) {
                            const clean = line.replace(/.*inquiry from tm[:：\\s]*/i, "").trim();
                            if (clean && clean !== "In...") {
                                lastMessage = clean;
                                break;
                            }
                        } else if (line !== buyerName && line.length > 5 &&
                                   !line.includes("询价单号") && !line.includes("时间") &&
                                   !line.includes("洽谈中") && !line.includes("TM 商机") &&
                                   !line.includes("User name") && !line.includes("查看详情")) {
                            lastMessage = line;
                            break;
                        }
                    }

                    const isUnread = text.includes("待回复") || text.includes("未读");
                    const status = text.includes("待回复") ? "待回复" : (text.includes("洽谈中") ? "洽谈中" : "已跟进");
                    const category = text.includes("TM 商机") ? "TM 商机" : "询盘";

                    list.push({
                        buyer_name: buyerName || "Unknown Buyer",
                        country: country,
                        inquiry_id: inquiryId,
                        last_message: lastMessage,
                        last_time: updateMatch ? updateMatch[1] : (createMatch ? createMatch[1] : ""),
                        create_time: createMatch ? createMatch[1] : "",
                        status: status,
                        category: category,
                        unread_count: isUnread ? 1 : 0,
                        has_unread: isUnread
                    });
                }

                const seen = new Set();
                const uniqueList = [];
                for (const item of list) {
                    const key = item.inquiry_id || item.buyer_name;
                    if (!seen.has(key)) {
                        seen.add(key);
                        uniqueList.push(item);
                    }
                }
                return uniqueList;
            }
            """

            inquiries = []
            if self.page:
                try:
                    inquiries = await self.page.evaluate(inquiry_extract_script)
                except Exception:
                    pass

            if isinstance(inquiries, list) and len(inquiries) > 0:
                for item in inquiries:
                    inq_id = str(item.get("inquiry_id") or "").strip()
                    c_val = str(item.get("country") or "").strip()
                    if inq_id and c_val:
                        self._inquiry_countries[inq_id] = c_val

                return {
                    "success": True,
                    "status": "READY",
                    "message": f"成功获取 {len(inquiries[:limit])} 个商机会话",
                    "data": {
                        "conversations": inquiries[:limit],
                        "total": len(inquiries[:limit]),
                        "elapsed_seconds": round(time.time() - start_time, 2)
                    }
                }

            # 备选方式：若处于传统 IM 独立聊天面板，使用列表项选择器
            item_selector = ".session-item, .contact-item, .im-session-list .item, [data-testid='conversation-item']"
            items = await self.page.query_selector_all(item_selector) if self.page else []
            
            conversations = []
            for item in items[:limit]:
                name_el = await item.query_selector(".name, .title, .buyer-name, .nick, [data-testid='contact-name']")
                buyer_name = (await name_el.inner_text()).strip() if name_el else "Unknown"

                # 提取国家/地区
                country_el = await item.query_selector(
                    ".country, .region, .nation, [class*='country'], [class*='flag'], [data-country]"
                )
                country = ""
                if country_el:
                    try:
                        title_val = await country_el.get_attribute("title")
                    except Exception:
                        title_val = None
                    try:
                        alt_val = await country_el.get_attribute("alt")
                    except Exception:
                        alt_val = None
                    if title_val and isinstance(title_val, str) and title_val.strip():
                        country = title_val.strip()
                    elif alt_val and isinstance(alt_val, str) and alt_val.strip():
                        country = alt_val.strip()

                    if not country:
                        try:
                            it = await country_el.inner_text()
                            if it and isinstance(it, str) and it.strip():
                                country = it.strip()
                        except Exception:
                            pass

                    if not country:
                        try:
                            src_val = await country_el.get_attribute("src")
                            if src_val and isinstance(src_val, str):
                                code_m = re.search(r"/([a-zA-Z]{2})\.(?:png|jpg|svg|webp|gif)", src_val)
                                if code_m:
                                    country = code_m.group(1).upper()
                        except Exception:
                            pass

                msg_el = await item.query_selector(".snippet, .text, .last-msg, .preview, .message-preview")
                last_msg = (await msg_el.inner_text()).strip() if msg_el else ""

                time_el = await item.query_selector(".time, .date, .last-time")
                last_time = (await time_el.inner_text()).strip() if time_el else ""

                badge_el = await item.query_selector(".badge, .unread-count, .unread-badge, .dot")
                unread_count = 0
                has_unread = False
                if badge_el:
                    badge_text = (await badge_el.inner_text()).strip()
                    if badge_text.isdigit():
                        unread_count = int(badge_text)
                        has_unread = unread_count > 0
                    else:
                        has_unread = True
                        unread_count = 1

                conversations.append({
                    "buyer_name": buyer_name,
                    "country": country,
                    "last_message": last_msg,
                    "last_time": last_time,
                    "unread_count": unread_count,
                    "has_unread": has_unread
                })

            return {
                "success": True,
                "status": "READY",
                "message": f"成功获取 {len(conversations)} 个最近会话",
                "data": {
                    "conversations": conversations,
                    "total": len(conversations),
                    "elapsed_seconds": round(time.time() - start_time, 2)
                }
            }
        except Exception as e:
            return {
                "success": False,
                "status": SendResultStatus.SEND_FAILED,
                "message": f"获取会话列表异常: {str(e)}",
                "data": {"conversations": [], "elapsed_seconds": round(time.time() - start_time, 2)}
            }
        finally:
            self.is_busy = False

    async def _navigate_conversation_page(self, page_number: int) -> bool:
        """Navigate the inquiry list to a specific page using button clicks or jump inputs."""
        if not self.page:
            return False

        curr_page = await self._get_current_page_number()
        if curr_page == page_number:
            return True

        # 1. 优先尝试点击具体页码按钮（如包含数字 "2" 的分页项）
        page_selectors = [
            f".next-pagination-item:not(.next-current):text-is('{page_number}')",
            f"button.next-pagination-item:text-is('{page_number}')",
            f"li.next-pagination-item[data-page='{page_number}']",
            f"[data-page='{page_number}']",
            f".ui2-pagination-pages a:text-is('{page_number}')",
            f"a[data-page='{page_number}']",
        ]
        for sel in page_selectors:
            try:
                el = await self.page.query_selector(sel)
                if el and await el.is_visible():
                    await el.scroll_into_view_if_needed()
                    await el.click()
                    await asyncio.sleep(2.5)
                    return True
            except Exception:
                continue

        # 2. 如果目标是下一页 (page_number == curr_page + 1)
        if page_number == curr_page + 1:
            next_selectors = [
                ".next-pagination-item.next-next:not([disabled]):not(.next-disabled)",
                "button.next-next:not([disabled])",
                "button:has-text('下一页'):not([disabled])",
                "button[aria-label='下一页']:not([disabled])",
                "button[aria-label='Next page']:not([disabled])",
                ".next-pagination-list button:has-text('下一页')",
                ".ui2-pagination-next:not(.disabled)",
                "a[rel='next']",
                "[mc-role='btn-next-page']",
                "button:has-text('>')",
            ]
            for sel in next_selectors:
                try:
                    btn = await self.page.query_selector(sel)
                    if btn and await btn.is_visible():
                        is_disabled = await btn.get_attribute("disabled")
                        class_attr = await btn.get_attribute("class") or ""
                        aria_disabled = await btn.get_attribute("aria-disabled")
                        if is_disabled is not None or "disabled" in class_attr or aria_disabled == "true":
                            continue
                        await btn.scroll_into_view_if_needed()
                        await btn.click()
                        await asyncio.sleep(2.5)
                        return True
                except Exception:
                    continue

        # 3. 如果目标是上一页 (page_number == curr_page - 1)
        if page_number == curr_page - 1:
            prev_selectors = [
                ".next-pagination-item.next-prev:not([disabled]):not(.next-disabled)",
                "button.next-prev:not([disabled])",
                "button:has-text('上一页'):not([disabled])",
                "button[aria-label='上一页']:not([disabled])",
                ".ui2-pagination-prev:not(.disabled)",
                "a[rel='prev']",
                "button:has-text('<')",
            ]
            for sel in prev_selectors:
                try:
                    btn = await self.page.query_selector(sel)
                    if btn and await btn.is_visible():
                        is_disabled = await btn.get_attribute("disabled")
                        class_attr = await btn.get_attribute("class") or ""
                        aria_disabled = await btn.get_attribute("aria-disabled")
                        if is_disabled is not None or "disabled" in class_attr or aria_disabled == "true":
                            continue
                        await btn.scroll_into_view_if_needed()
                        await btn.click()
                        await asyncio.sleep(2.5)
                        return True
                except Exception:
                    continue

        # 4. 尝试使用页码跳转输入框
        try:
            jump_input = await self.page.query_selector(
                ".next-pagination-jump-input input, .ui2-pagination-jump-input input, input[aria-label*='页']"
            )
            if jump_input and await jump_input.is_visible():
                await jump_input.scroll_into_view_if_needed()
                await jump_input.fill(str(page_number))
                await jump_input.press("Enter")
                await asyncio.sleep(2.5)
                new_page = await self._get_current_page_number()
                if new_page == page_number:
                    return True
        except Exception:
            pass

        return False

    async def iter_conversations_pages(self, max_pages: int = 1000):
        """Yield conversations page by page without leaving the current page until its items are consumed."""
        if max_pages < 1:
            raise ValueError("max_pages must be positive")
        seen_pages, seen_inquiries = set(), set()
        for page_number in range(1, max_pages + 1):
            if page_number > 1:
                nav_ok = await self._navigate_conversation_page(page_number)
                if not nav_ok and self.page:
                    break
            result = await self.get_recent_conversations(limit=1000)
            if not result.get("success"):
                break
            conversations = result.get("data", {}).get("conversations", [])
            if not conversations:
                break
            signature = tuple(str(item.get("inquiry_id") or item.get("buyer_name") or "") for item in conversations)
            if signature in seen_pages:
                break
            seen_pages.add(signature)
            page_unique = []
            for conversation in conversations:
                inquiry_id = str(conversation.get("inquiry_id") or "")
                key = inquiry_id or str(conversation.get("buyer_name") or "")
                if key and key not in seen_inquiries:
                    seen_inquiries.add(key)
                    page_unique.append(conversation)
            if page_unique:
                yield page_unique

    async def get_all_conversations(self, max_pages: int = 1000) -> List[Dict[str, Any]]:
        """Read bounded inquiry pages, stopping before empty/repeated page loops."""
        if max_pages < 1:
            raise ValueError("max_pages must be positive")
        all_conversations: List[Dict[str, Any]] = []
        seen_pages, seen_inquiries = set(), set()
        for page_number in range(1, max_pages + 1):
            if page_number > 1:
                nav_ok = await self._navigate_conversation_page(page_number)
                if not nav_ok and self.page:
                    # 真实浏览器中无法继续翻页，说明已到达最后一页
                    break
            result = await self.get_recent_conversations(limit=1000)
            if not result.get("success"):
                raise RuntimeError(str(result.get("status", "conversation extraction failed")))
            conversations = result.get("data", {}).get("conversations", [])
            if not conversations:
                break
            signature = tuple(str(item.get("inquiry_id") or item.get("buyer_name") or "") for item in conversations)
            if signature in seen_pages:
                # 页面内容与之前页面完全相同，说明已到尾页或翻页无变化
                break
            seen_pages.add(signature)
            for conversation in conversations:
                inquiry_id = str(conversation.get("inquiry_id") or "")
                key = inquiry_id or str(conversation.get("buyer_name") or "")
                if key and key not in seen_inquiries:
                    seen_inquiries.add(key)
                    all_conversations.append(conversation)
        else:
            raise RuntimeError("conversation pagination reached max_pages")
        return all_conversations

    async def get_sync_history(self, inquiry_id: str, buyer_name: Optional[str] = None):
        """Adapt the existing complete history reader to the CRM-safe SyncMessage contract."""
        from alibaba_messenger.sync_models import SyncMessage

        result = await self.get_chat_history(buyer_name=buyer_name, inquiry_id=inquiry_id, limit=0, order="asc")
        if not result.get("success"):
            raise RuntimeError(str(result.get("status", "history extraction failed")))
        converted = []
        for sequence, raw in enumerate(result.get("data", {}).get("messages", []), start=1):
            message = SyncMessage.from_source(
                inquiry_id=inquiry_id, sender=raw.get("sender", "buyer"), content=raw.get("content", ""),
                raw_time=raw.get("raw_time") or raw.get("time", ""), sequence=sequence,
                platform_id=raw.get("platform_id") or raw.get("platformId"),
                message_type=raw.get("type", "chat"), translation=raw.get("translation", ""),
            )
            if message is not None:
                converted.append(message)
        return converted

    async def _extract_dialogue_messages(
        self,
        page,
        limit: int = 0,
        order: str = "asc",
        buyer_name: str = ""
    ) -> List[Dict[str, Any]]:
        """从商机详情页(maDetail.htm)或对话抽屉中深度解析双方完整往来消息，支持自动拉取更早历史与深度清洗"""
        if not page:
            return []
        try:
            # 1. 尝试反复向上滚动与点击“查看更多历史消息”，加载全部更早历史
            for _ in range(6):
                try:
                    expanded = await page.evaluate("""
                    () => {
                        let acted = false;
                        // 点击“查看更多历史消息”或“加载更多”
                        const loadMoreBtns = Array.from(document.querySelectorAll("button, a, span, div")).filter(el => {
                            const t = el.innerText ? el.innerText.trim() : "";
                            return (t === "查看更多历史消息" || t === "查看更早记录" || t === "更早消息" || 
                                    t === "加载更多" || t.toLowerCase().includes("load more") || 
                                    t.toLowerCase().includes("earlier")) &&
                                   el.offsetWidth > 0 && el.offsetHeight > 0;
                        });
                        for (const btn of loadMoreBtns) {
                            try { btn.click(); acted = true; } catch(e) {}
                        }

                        // 找到消息列表可滚动容器，向上滚动以触发更早历史消息增量加载
                        const scrollContainers = Array.from(document.querySelectorAll("div, ul, section")).filter(d => 
                            d.scrollHeight > d.clientHeight && d.clientHeight > 180 &&
                            d.querySelector("[class*='message'], [class*='chat'], [class*='bubble'], [class*='record'], [class*='timeline']")
                        );
                        for (const sc of scrollContainers) {
                            if (sc.scrollTop > 0) {
                                sc.scrollTop = Math.max(0, sc.scrollTop - 600);
                                acted = true;
                            }
                        }
                        return acted;
                    }
                    """)
                    if expanded:
                        await asyncio.sleep(1.0)
                    else:
                        break
                except Exception:
                    break

            # 2. 深度提取气泡消息列表及原始询价单主体卡片
            extract_script = """
            (targetBuyer) => {
                // 2.1 提取首条原始询盘单据卡片 (若存在)
                let initialCard = null;
                const cardSelectors = [
                    ".inquiry-detail", ".rfq-detail", ".feedback-detail",
                    "[class*='inquiry-detail']", "[class*='detail-content-wrap']",
                    "[class*='inquiry-info']", "[class*='product-info']", ".spec-inquiry-detail"
                ];
                for (const sel of cardSelectors) {
                    const el = document.querySelector(sel);
                    if (el) {
                        let ct = el.innerText ? el.innerText.trim() : "";
                        if (ct && ct.length > 20 && !ct.includes("聊天记录")) {
                            ct = ct.replace(/(查看详情|回复|添加备忘|转发|举报|由阿里翻译提供[\\s\\S]*?(反馈|$))/g, "").trim();
                            if (ct) {
                                initialCard = {
                                    sender: "buyer",
                                    content: ct,
                                    translation: "",
                                    time: "",
                                    type: "initial_inquiry"
                                };
                                break;
                            }
                        }
                    }
                }

                // 2.2 提取所有往来消息气泡
                let currentDate = "";
                const dividers = Array.from(document.querySelectorAll("[class*='date'], [class*='time-divider'], [class*='timeline-date'], .time-line-item"));
                for (const d of dividers) {
                    const dtMatch = (d.innerText || "").match(/(\\d{4}[-/.]\\d{1,2}[-/.]\\d{1,2})/);
                    if (dtMatch) {
                        currentDate = dtMatch[1].replace(/[/.]/g, "-");
                        break;
                    }
                }

                const bubbleSelectors = [
                    ".im-message-item", ".message-bubble", ".chat-message",
                    ".inquiry-record-item", ".negotiation-item", ".timeline-item",
                    "[class*='message-item']", "[class*='chat-item']", "[class*='record-item']",
                    ".buyer-content", ".supplier-content", ".detail-content"
                ];
                let items = Array.from(document.querySelectorAll(bubbleSelectors.join(", ")));
                
                if (items.length === 0) {
                    items = Array.from(document.querySelectorAll("div[class*='content'], div[class*='desc'], p[class*='text']")).filter(el => {
                        const t = el.innerText ? el.innerText.trim() : "";
                        return t.length > 5 && !t.includes("询价单号") && !t.includes("更新时间") && !t.includes("Copyright");
                    });
                }

                const bubbles = [];
                for (const item of items) {
                    // 排除侧边栏、客户卡片、建议反馈等非聊天流容器内的元素
                    if (item.closest(".customer-info, .detail-right, [class*='sidebar'], [class*='drawer-right'], .feedback-box, [class*='footer'], [class*='header'], [class*='tool-bar'], .next-tabs")) {
                        continue;
                    }

                    const rawText = item.innerText ? item.innerText.trim() : "";
                    if (!rawText || rawText.length < 2) continue;

                    // 过滤页面非聊天悬浮/小部件噪音文本
                    if (
                        rawText.includes("未读人脉") || (rawText.includes("人脉") && rawText.length < 10) ||
                        rawText.includes("算法选品") || rawText.includes("快速锁定主推款") ||
                        rawText.includes("欢迎提交贵建议") || rawText.includes("欢迎提宝贵建议") ||
                        rawText.includes("名片申请已发出") || rawText.includes("等待对方通过") ||
                        rawText.includes("近90天站内行为") || rawText.includes("跟进管理") ||
                        rawText.includes("加为客户") || rawText.includes("客户行为数据") ||
                        (rawText.includes("查看详情") && rawText.length < 10) ||
                        /^(已读|未读|read|unread|反馈)$/i.test(rawText.trim())
                    ) {
                        continue;
                    }

                    // 识别发送者与系统消息
                    const itemClass = (item.className || "") + " " + (item.parentElement ? item.parentElement.className : "");
                    const isSystem = /自动接待将不再触发|自动接待已停止|介入该会话|系统提示|等待对方同意|已分配给|转交给了/i.test(rawText) ||
                                     /system|notice|event|action-tip/i.test(itemClass);
                    
                    const isSeller = /seller|mine|right|supplier|my-msg/i.test(itemClass) ||
                                     rawText.startsWith("我：") || rawText.startsWith("Me:") ||
                                     rawText.includes("自动接待发送");

                    let sender = "buyer";
                    if (isSystem) {
                        sender = "system";
                    } else if (isSeller) {
                        sender = "seller";
                    }

                    // 提取时间戳
                    const timeEl = item.querySelector("[class*='time'], [class*='date'], [class*='timestamp']");
                    let timeStr = timeEl ? timeEl.innerText.trim() : "";
                    if (!timeStr && item.previousElementSibling && /time|date|timestamp/i.test(item.previousElementSibling.className || "")) {
                        timeStr = item.previousElementSibling.innerText.trim();
                    }
                    if (!timeStr) {
                        const timeMatch = rawText.match(/(\\d{4}[-/.]\\d{1,2}[-/.]\\d{1,2}\\s+\\d{1,2}:\\d{1,2}(:\\d{1,2})?|\\d{1,2}:\\d{1,2})/);
                        timeStr = timeMatch ? timeMatch[0] : "";
                    }

                    // 日期继承与规范化
                    const fullDateMatch = timeStr.match(/^(\\d{4}[-/.]\\d{1,2}[-/.]\\d{1,2})\\s+(\\d{1,2}:\\d{1,2}(:\\d{1,2})?)/);
                    if (fullDateMatch) {
                        currentDate = fullDateMatch[1].replace(/[/.]/g, "-");
                        timeStr = `${currentDate} ${fullDateMatch[2]}`;
                    } else if (/^\\d{1,2}:\\d{1,2}(:\\d{1,2})?$/.test(timeStr) && currentDate) {
                        timeStr = `${currentDate} ${timeStr}`;
                    }

                    // 提取独立翻译元素（若页面直接有翻译子节点）
                    const transEl = item.querySelector("[class*='translate'], [class*='trans-'], [class*='translation'], .f-trans");
                    let isolatedTrans = "";
                    if (transEl) {
                        isolatedTrans = transEl.innerText.replace(/由阿里翻译提供[\\s\\S]*?(反馈|$)/gi, "").trim();
                    }

                    // 清洗原始文本
                    let cleaned = rawText;
                    if (timeStr && cleaned.includes(timeStr)) {
                        cleaned = cleaned.replace(timeStr, "").trim();
                    }
                    const hasAlibabaTrans = cleaned.includes("由阿里翻译提供");
                    cleaned = cleaned.replace(/由阿里翻译提供[\\s\\S]*?(反馈|$)/gi, "").trim();
                    cleaned = cleaned.replace(/自动接待发送[，,]?[\\s\\n]*去优化/gi, "").trim();
                    cleaned = cleaned.replace(/自动接待发送/gi, "").trim();
                    cleaned = cleaned.replace(/(^|\\n)\\s*(已读|未读|Read|Unread)\\s*($|\\n)/gi, "\\n").trim();

                    // 按行分析，剔除头像单字和名称
                    let lines = cleaned.split("\\n").map(s => s.trim()).filter(Boolean);
                    let filteredLines = [];
                    for (const line of lines) {
                        if (line === "User name") continue;
                        if (targetBuyer && line.toLowerCase() === targetBuyer.toLowerCase()) continue;
                        if (line.length === 1 && /^[A-Za-z0-9]$/.test(line)) continue;
                        if (/^(已读|未读|Read|Unread)$/i.test(line)) continue;
                        filteredLines.push(line);
                    }

                    let content = filteredLines.join("\\n").trim();
                    let translation = isolatedTrans;

                    // 若未找到独立翻译节点但含阿里翻译文本，进行中英文段落拆分
                    if (!translation && hasAlibabaTrans && filteredLines.length >= 2) {
                        const half = Math.floor(filteredLines.length / 2);
                        const part1 = filteredLines.slice(0, half).join("\\n").trim();
                        const part2 = filteredLines.slice(half).join("\\n").trim();
                        if (part1 && part2) {
                            content = part1;
                            translation = part2;
                        }
                    }

                    if (content) {
                        bubbles.push({
                            sender: sender,
                            content: content,
                            translation: translation || "",
                            time: timeStr
                        });
                    }
                }
                return {
                    initialCard: initialCard,
                    bubbles: bubbles
                };
            }
            """
            extracted = await page.evaluate(extract_script, buyer_name)
            if not isinstance(extracted, dict):
                return []

            initial_card = extracted.get("initialCard")
            bubbles = extracted.get("bubbles") or []

            # 3. 时间正序校准
            def parse_time_token(t_str):
                import re
                if not t_str:
                    return ""
                m = re.search(r'(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})(?:\s+(\d{1,2}):(\d{1,2}))?', t_str)
                if m:
                    y, mon, d, h, mi = m.groups()
                    h = h or "00"
                    mi = mi or "00"
                    return f"{int(y):04d}-{int(mon):02d}-{int(d):02d} {int(h):02d}:{int(mi):02d}"
                m_time = re.search(r'(\d{1,2}):(\d{1,2})', t_str)
                if m_time:
                    h, mi = m_time.groups()
                    return f"0000-00-00 {int(h):02d}:{int(mi):02d}"
                return t_str

            times = [parse_time_token(m.get("time")) for m in bubbles if m.get("time")]
            # 仅当首尾消息具有可比完整时间戳且首条严格晚于末条时（证明 DOM 为倒序展示），才反转为时间正序
            if len(times) >= 2:
                valid_times = [t for t in times if not t.startswith("0000-00-00")]
                if len(valid_times) >= 2 and valid_times[0] > valid_times[-1]:
                    bubbles.reverse()
                elif len(times) == len(bubbles) and all(t.startswith("0000-00-00") for t in times) and times[0] > times[-1]:
                    bubbles.reverse()

            # 将首条原始单据需求插在会话最开始
            final_msgs = []
            if initial_card:
                final_msgs.append(initial_card)
            final_msgs.extend(bubbles)

            # 4. 根据 limit 截取
            # 正序下，若 limit > 0，保留最新的 limit 条记录（末尾 N 条）
            if limit > 0 and len(final_msgs) > limit:
                final_msgs = final_msgs[-limit:]

            # 5. 根据 requested order 返回
            if order == "desc":
                final_msgs.reverse()

            return final_msgs
        except Exception as e:
            print(f"[Bot] 提取聊天历史气泡异常: {e}")
            return []

    async def _extract_country_from_page(self, page_obj) -> str:
        """从页面或抽屉 DOM 中提取买家国家/地区"""
        if not page_obj:
            return ""
        try:
            return await page_obj.evaluate("""() => {
                const flagCandidates = Array.from(document.querySelectorAll(
                    "[class*='country'], [class*='region'], [class*='nation'], " +
                    "img[src*='flag'], img[src*='country'], [data-country], [data-country-code]"
                ));
                for (const el of flagCandidates) {
                    const cls = (el.className || "").toString().toLowerCase();
                    const src = (el.getAttribute("src") || "").toLowerCase();
                    if (cls.includes("avatar") || src.includes("avatar") || cls.includes("logo") || src.includes("product")) {
                        continue;
                    }
                    const dataCode = el.getAttribute("data-country-code") || el.getAttribute("data-country") || el.getAttribute("data-code");
                    if (dataCode && dataCode.trim().length >= 2 && dataCode.trim().length <= 40) return dataCode.trim();
                    const titleVal = (el.getAttribute("title") || el.getAttribute("alt") || el.getAttribute("aria-label") || "").trim();
                    const titleLower = titleVal.toLowerCase();
                    if (titleVal && !titleLower.includes("avatar") && !titleLower.includes("logo") && !titleLower.includes("icon") && !titleLower.includes("image")) {
                        return titleVal;
                    }
                    const srcMatch = src.match(/\\/([a-z]{2})\\.(png|jpg|svg|webp|gif)/i);
                    if (srcMatch) return srcMatch[1].toUpperCase();
                    const classMatch = cls.match(/(?:flag|nation|country|fi)[-_]([a-z]{2})\b/i);
                    if (classMatch) return classMatch[1].toUpperCase();
                    const inner = el.innerText ? el.innerText.trim() : "";
                    if (inner && inner.length >= 2 && inner.length <= 40 && !inner.toLowerCase().includes("inquiry")) return inner;
                }
                const text = document.body ? document.body.innerText : "";
                const countryMatch = text.match(/(?:国家\\/地区|国家|地区|Country\\/Region|Country|Region)[:：\\s]*([a-zA-Z\\u4e00-\\u9fa5\\s]{2,40})/i);
                return countryMatch ? countryMatch[1].trim() : "";
            }""") or ""
        except Exception:
            return ""

    async def get_chat_history(
        self,
        buyer_name: Optional[str] = None,
        inquiry_id: Optional[str] = None,
        limit: int = 0,
        order: str = "asc"
    ) -> Dict[str, Any]:
        """获取指定买家或商机ID的完整聊天历史记录"""
        if not self.is_logged_in:
            return {
                "success": False,
                "status": SendResultStatus.NEED_LOGIN,
                "message": "国际站尚未登录，请先在界面完成登录",
                "data": {"buyer_name": buyer_name or "", "inquiry_id": inquiry_id or "", "messages": []}
            }

        start_time = time.time()
        self.is_busy = True
        try:
            await self._close_unexpected_dialogs()

            # 方式 A：在商机沟通列表中跨页检索目标行（支持切页换地址与翻页点击）
            buyer_target, found_page = await self._find_inquiry_row(buyer_name=buyer_name, inquiry_id=inquiry_id)

            if isinstance(buyer_target, dict) and buyer_target.get("found"):
                matched_id = buyer_target.get("inquiry_id") or inquiry_id
                real_buyer_name = buyer_target.get("buyer_name") or buyer_name or "Unknown Buyer"
                snippet = buyer_target.get("last_message")
                last_time = buyer_target.get("last_time")
                target_idx = buyer_target.get("index", 0)

                detail_links = await self.page.query_selector_all("a.actions-view-detail, .actions-view-detail") if self.page else []
                messages = []
                detail_page = None
                detail_country = ""
                btn = None

                if target_idx < len(detail_links):
                    btn = detail_links[target_idx]
                elif self.page:
                    detail_locators = await self.page.locator("a, button, span").filter(has_text="查看详情").all()
                    if target_idx < len(detail_locators):
                        btn = detail_locators[target_idx]

                if btn:
                    try:
                        if self.context:
                            try:
                                async with self.context.expect_page(timeout=5000) as new_page_info:
                                    await btn.click()
                                detail_page = await new_page_info.value
                            except Exception:
                                href = buyer_target.get("href")
                                if href:
                                    full_url = href if href.startswith("http") else (f"https:{href}" if href.startswith("//") else f"https://message.alibaba.com{href}")
                                    detail_page = await self.context.new_page()
                                    await detail_page.goto(full_url, wait_until="domcontentloaded", timeout=15000)

                            if detail_page:
                                await detail_page.wait_for_load_state("domcontentloaded")
                                await asyncio.sleep(2.0)
                                try:
                                    ss_path = os.path.join(settings.SCREENSHOTS_DIR, f"detail_{matched_id or 'last'}.png")
                                    await detail_page.screenshot(path=ss_path)
                                except Exception:
                                    pass
                                detail_country = await self._extract_country_from_page(detail_page)
                                messages = await self._extract_dialogue_messages(detail_page, limit=limit, order=order, buyer_name=real_buyer_name)
                                await detail_page.close()
                        elif self.page:
                            await btn.click()
                            await asyncio.sleep(2.0)
                            detail_country = await self._extract_country_from_page(self.page)
                            messages = await self._extract_dialogue_messages(self.page, limit=limit, order=order, buyer_name=real_buyer_name)
                    except Exception as ex:
                        print(f"[Bot] 打开商机详情页异常: {ex}")

                # 兜底：若详情页抽屉未提取到气泡，则使用商机卡片中已提取的最新往来消息
                if not messages and snippet:
                    messages = [{
                        "sender": "buyer",
                        "content": snippet,
                        "translation": "",
                        "time": last_time
                    }]

                final_country = detail_country or str(buyer_target.get("country") or "").strip() or self.get_last_extracted_country(matched_id)
                if matched_id and final_country:
                    self._inquiry_countries[str(matched_id)] = final_country

                return {
                    "success": True,
                    "status": "READY",
                    "message": f"成功获取买家 [{real_buyer_name}] 的完整会话记录 (共 {len(messages)} 条)",
                    "data": {
                        "buyer_name": real_buyer_name,
                        "inquiry_id": matched_id,
                        "country": final_country,
                        "messages": messages,
                        "total": len(messages),
                        "elapsed_seconds": round(time.time() - start_time, 2)
                    }
                }

            # 方式 B：当前处于独立 IM 聊天面板，或需要全局检索
            search_query = buyer_name or inquiry_id or ""
            search_selector = "input[type='text']:not([readonly]), input[placeholder*='搜索']:not([readonly]), input[placeholder*='Search']:not([readonly])"
            search_input = None
            if self.page:
                try:
                    search_input = await self.page.wait_for_selector(search_selector, timeout=5000)
                except Exception:
                    search_input = None

            if not search_input:
                target_desc = f"买家 [{buyer_name}]" if buyer_name else f"商机ID [{inquiry_id}]"
                return {
                    "success": False,
                    "status": SendResultStatus.BUYER_NOT_FOUND,
                    "message": f"未在商机列表中找到{target_desc}",
                    "data": {"buyer_name": buyer_name or "", "inquiry_id": inquiry_id or "", "country": self.get_last_extracted_country(inquiry_id) or "", "messages": [], "elapsed_seconds": round(time.time() - start_time, 2)}
                }

            await search_input.click()
            await search_input.fill("")
            for char in search_query:
                await self.page.keyboard.type(char)
                await asyncio.sleep(0.03)
            await self.page.keyboard.press("Enter")
            await asyncio.sleep(1.5)

            first_item = await self.page.wait_for_selector(".session-item, .contact-item, .im-session-list .item, [data-testid='conversation-item']", timeout=settings.SEARCH_TIMEOUT_MS)
            await first_item.click()
            await asyncio.sleep(1.0)

            bubbles = await self.page.query_selector_all(".im-message-item, .message-bubble, .bubble-item, .chat-message") if self.page else []
            messages = []
            slice_bubbles = bubbles if limit <= 0 else bubbles[-limit:]
            for b in slice_bubbles:
                class_attr = await b.get_attribute("class") or ""
                is_mine = "mine" in class_attr or "bubble-right" in class_attr or "right" in class_attr or "self" in class_attr
                sender = "seller" if is_mine else "buyer"

                text_el = await b.query_selector(".text, .content, .message-text, .msg-text")
                content = (await text_el.inner_text()).strip() if text_el else ""

                time_el = await b.query_selector(".time, .message-time, .msg-time")
                msg_time = (await time_el.inner_text()).strip() if time_el else ""

                if content:
                    messages.append({
                        "sender": sender,
                        "content": content,
                        "time": msg_time
                    })

            await self._clear_search()
            return {
                "success": True,
                "status": "READY",
                "message": f"成功获取与买家 [{buyer_name or search_query}] 的 {len(messages)} 条历史消息",
                "data": {
                    "buyer_name": buyer_name or search_query,
                    "inquiry_id": inquiry_id or "",
                    "country": self.get_last_extracted_country(inquiry_id) or "",
                    "messages": messages,
                    "total": len(messages),
                    "elapsed_seconds": round(time.time() - start_time, 2)
                }
            }
        except Exception as e:
            await self._clear_search()
            return {
                "success": False,
                "status": SendResultStatus.SEND_FAILED,
                "message": f"获取聊天历史异常: {str(e)}",
                "data": {"buyer_name": buyer_name, "inquiry_id": inquiry_id or "", "country": self.get_last_extracted_country(inquiry_id) or "", "messages": [], "elapsed_seconds": round(time.time() - start_time, 2)}
            }
        finally:
            self.is_busy = False

    async def get_buyer_profile(self, buyer_name: Optional[str] = None, inquiry_id: Optional[str] = None) -> dict:
        """获取买家详细画像（包含国家/地区、姓名、商机ID等）"""
        target_id = str(inquiry_id or "").strip()
        target_name = (buyer_name or "").strip()
        cached_country = self.get_last_extracted_country(target_id) if target_id else ""
        
        # 若已有缓存国家且同时有姓名与ID，直接返回
        if cached_country and target_name and target_id:
            return {
                "success": True,
                "status": "READY",
                "message": f"成功获取买家 [{target_name}] 资料",
                "data": {
                    "inquiry_id": target_id,
                    "buyer_name": target_name,
                    "country": cached_country
                }
            }

        # 尝试通过 _find_inquiry_row 定位商机并提取信息
        row_info, _ = await self._find_inquiry_row(buyer_name=target_name, inquiry_id=target_id)
        if row_info and row_info.get("found"):
            b_name = row_info.get("buyer_name") or target_name
            inq_id = row_info.get("inquiry_id") or target_id
            country = row_info.get("country") or cached_country
            if inq_id and country:
                self._inquiry_countries[str(inq_id)] = country
            return {
                "success": True,
                "status": "READY",
                "message": f"成功获取买家 [{b_name}] 资料",
                "data": {
                    "inquiry_id": inq_id,
                    "buyer_name": b_name,
                    "country": country,
                    "last_time": row_info.get("last_time", ""),
                    "last_message": row_info.get("last_message", "")
                }
            }

        return {
            "success": False,
            "status": SendResultStatus.BUYER_NOT_FOUND,
            "message": f"未在商机列表中找到目标买家资料",
            "data": {
                "inquiry_id": target_id,
                "buyer_name": target_name,
                "country": cached_country
            }
        }

    async def _clear_search(self):
        """点击搜索栏清除按钮恢复初始列表"""
        if not self.page:
            return
        try:
            clear_btn = await self.page.query_selector(".search-clear, .icon-close, .btn-clear")
            if clear_btn and await clear_btn.is_visible():
                await clear_btn.click()
        except Exception:
            pass

    async def close(self):
        if self.context:
            try:
                await self.context.close()
            except Exception:
                pass
            finally:
                self.context = None
        if self.playwright:
            try:
                await self.playwright.stop()
            except Exception:
                pass
            finally:
                self.playwright = None

bot = AlibabaMessengerBot()
