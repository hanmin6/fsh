# -*- coding: utf-8 -*-
import asyncio
import json
from playwright.async_api import async_playwright
from alibaba_messenger.config import settings

async def main():
    p = await async_playwright().start()
    args = [
        "--disable-blink-features=AutomationControlled",
        "--no-sandbox",
        "--disable-infobars"
    ]
    context = await p.chromium.launch_persistent_context(
        user_data_dir=settings.PROFILE_DIR,
        headless=False,
        viewport={"width": 1280, "height": 800},
        args=args
    )
    page = context.pages[0] if context.pages else await context.new_page()
    await page.goto("https://message.alibaba.com/message/default.htm", wait_until="domcontentloaded", timeout=30000)
    await asyncio.sleep(2)

    page2_btn = await page.query_selector("a[data-page='2'], [mc-role='btn-next-page']")
    if page2_btn:
        await page2_btn.click()
        await asyncio.sleep(2.5)

    detail_links = await page.query_selector_all("a.actions-view-detail, .actions-view-detail")
    btn = detail_links[7]

    async with context.expect_page(timeout=5000) as new_page_info:
        await btn.click()
    target_page = await new_page_info.value
    await target_page.wait_for_load_state("domcontentloaded")
    await asyncio.sleep(2)

    holder = await target_page.query_selector(".holder, .mock-reply")
    if holder and await holder.is_visible():
        await holder.click()
        await asyncio.sleep(1.5)

    tinymce_body = target_page.frame_locator("#normal-im-send_ifr").locator("body")
    await tinymce_body.wait_for(timeout=4000)

    # 清空并输入正式内容
    await tinymce_body.evaluate("el => el.innerHTML = ''")
    await tinymce_body.click(force=True)
    await asyncio.sleep(0.3)

    approved_message = "Hello Dino, hope you are doing well! Please let us know if there is any update regarding the inquiry. Thank you!"
    for char in approved_message:
        await target_page.keyboard.type(char)
        await asyncio.sleep(0.015)

    await asyncio.sleep(1.5)

    # 准确查找可点击的橙色“发送”按钮
    send_candidates = await target_page.evaluate("""
    () => {
        return Array.from(document.querySelectorAll("div[data-clk='send'], .send, button")).filter(el => {
            const t = el.innerText ? el.innerText.trim() : "";
            return (t === "发送" || el.getAttribute("data-clk") === "send") && el.offsetWidth > 0 && el.offsetHeight > 0;
        }).map(el => ({
            tag: el.tagName,
            cls: el.className,
            dataClk: el.getAttribute("data-clk"),
            color: window.getComputedStyle(el).backgroundColor,
            rect: { w: el.offsetWidth, h: el.offsetHeight }
        }));
    }
    """)
    print("Send button candidates:", json.dumps(send_candidates, ensure_ascii=False, indent=2))

    # 点击真正的橙色发送按钮
    real_send_btn = await target_page.query_selector("div[data-clk='send'], .send[data-clk='send']")
    if not real_send_btn:
        real_send_btn = await target_page.query_selector(".send")
    
    if real_send_btn:
        print("Clicking real send button (data-clk='send')...")
        await real_send_btn.click()
        await asyncio.sleep(3)

    # 截图看最新发送结果
    await target_page.screenshot(path="alibaba_messenger/logs/screenshots/diagnose_after_real_send.png")
    print("Saved screenshot to alibaba_messenger/logs/screenshots/diagnose_after_real_send.png")

    await target_page.close()
    await context.close()
    await p.stop()

if __name__ == "__main__":
    asyncio.run(main())
