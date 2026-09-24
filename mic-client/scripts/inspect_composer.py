import asyncio
import re
import sys
from pathlib import Path

repo_src = Path(r"G:\FSH\made-in-china\made-in-china\src")
if str(repo_src) not in sys.path:
    sys.path.insert(0, str(repo_src))

from mic_gateway.browser.runtime import BrowserRuntime
from mic_gateway.config import get_settings

TARGET_URL = "https://membercenter.made-in-china.com/message/index.html#inbox/rwKpdOGJfYoM..from=list"

async def main():
    settings = get_settings().model_copy(update={"chromium_headless": False})
    runtime = BrowserRuntime(settings)
    await runtime.start()
    try:
        async def inspect(page):
            print(f"Opening target conversation URL directly: {TARGET_URL}")
            await page.goto(TARGET_URL, wait_until="domcontentloaded")
            await page.wait_for_timeout(5000)

            # Check if login required
            if "login" in page.url or "logon" in page.url:
                print("\n>>> 请在弹出的浏览器中登录账号并进入询盘后台...")
                await asyncio.to_thread(input, ">>> 登录完成后，请回到此处按回车键继续: ")
                await page.goto(TARGET_URL, wait_until="domcontentloaded")
                await page.wait_for_timeout(5000)

            print(f"\nCurrent URL: {page.url}")
            print(f"Page Title: {await page.title()}")

            # 1. Search all frames (iframes)
            print(f"\n--- 检查所有 Frame ({len(page.frames)}) ---")
            for idx, frame in enumerate(page.frames):
                f_name = frame.name
                f_url = frame.url
                print(f"Frame {idx}: name='{f_name}', url='{f_url}'")
                try:
                    tas = frame.locator("textarea, [contenteditable='true']")
                    ta_count = await tas.count()
                    if ta_count > 0:
                        print(f"  --> Frame {idx} 有输入框! count={ta_count}")
                        for i in range(ta_count):
                            el = tas.nth(i)
                            tag = await el.evaluate("el => el.tagName")
                            cls = await el.get_attribute("class")
                            ph = await el.get_attribute("placeholder")
                            print(f"      输入框 {i}: tag={tag}, class='{cls}', placeholder='{ph}'")
                    
                    send_btns = frame.locator("button, a, div, span").filter(has_text=re.compile(r"^(发送|发送消息|Send)$"))
                    s_count = await send_btns.count()
                    if s_count > 0:
                        print(f"  --> Frame {idx} 有发送按钮! count={s_count}")
                        for i in range(s_count):
                            b = send_btns.nth(i)
                            tag = await b.evaluate("el => el.tagName")
                            b_cls = await b.get_attribute("class")
                            b_txt = (await b.inner_text()).strip()
                            print(f"      发送按钮 {i}: tag={tag}, class='{b_cls}', text='{b_txt}'")
                except Exception as e:
                    print(f"  Frame {idx} query error: {e}")

            # 2. Search on main page for any element with "发送" or "发送消息"
            print("\n--- 检查主页面所有包含'发送'文字的元素 ---")
            send_candidates = page.locator("button, a, div, span, input[type='button'], input[type='submit']").filter(
                has_text=re.compile(r"发送")
            )
            count = await send_candidates.count()
            print(f"匹配到包含'发送'的元素数量: {count}")
            for i in range(min(count, 15)):
                el = send_candidates.nth(i)
                tag = await el.evaluate("el => el.tagName")
                cls = await el.get_attribute("class")
                txt = (await el.inner_text()).strip()
                vis = await el.is_visible()
                print(f"  候选 {i}: tag={tag}, class='{cls}', text='{txt}', visible={vis}")

            # 3. Search on main page for all inputs/textareas/contenteditables
            print("\n--- 检查主页面所有输入区域 ---")
            inputs = page.locator("textarea, [contenteditable='true'], input[type='text']")
            in_count = await inputs.count()
            print(f"主页面输入框数量: {in_count}")
            for i in range(in_count):
                el = inputs.nth(i)
                tag = await el.evaluate("el => el.tagName")
                cls = await el.get_attribute("class")
                ph = await el.get_attribute("placeholder")
                vis = await el.is_visible()
                box = await el.bounding_box()
                print(f"  输入框 {i}: tag={tag}, class='{cls}', placeholder='{ph}', visible={vis}, box={box}")

            # 4. Check if clicking "回复" (.btn-reply) is required to expand the editor
            reply_btn = page.locator("button.btn-reply, .btn-reply, button:has-text('回复')")
            reply_count = await reply_btn.count()
            print(f"\n'回复'按钮数量: {reply_count}")
            if reply_count > 0:
                print(f"点击'回复'按钮前，visible={await reply_btn.first.is_visible()}")
                # Try clicking reply
                print("尝试点击'回复'按钮...")
                await reply_btn.first.click()
                await page.wait_for_timeout(2000)

                # Check inputs again after clicking reply
                print("--- 点击'回复'按钮后再次检查输入区域 ---")
                inputs_after = page.locator("textarea, [contenteditable='true']")
                print(f"输入框数量: {await inputs_after.count()}")
                for i in range(await inputs_after.count()):
                    el = inputs_after.nth(i)
                    tag = await el.evaluate("el => el.tagName")
                    cls = await el.get_attribute("class")
                    vis = await el.is_visible()
                    print(f"  输入框 {i}: tag={tag}, class='{cls}', visible={vis}")

                send_after = page.locator("button, a, div").filter(has_text=re.compile(r"^(发送|发送消息|Send)$"))
                print(f"发送按钮数量: {await send_after.count()}")
                for i in range(await send_after.count()):
                    b = send_after.nth(i)
                    print(f"  发送按钮 {i}: tag={await b.evaluate('el => el.tagName')}, class='{await b.get_attribute('class')}', text='{(await b.inner_text()).strip()}', visible={await b.is_visible()}")

            print("\n>>> 检查完毕！请在终端查看输出。按回车键结束程序: ")
            await asyncio.to_thread(input)

        await runtime.run_serialized(inspect)
    finally:
        await runtime.stop()

if __name__ == "__main__":
    asyncio.run(main())
