import asyncio
import json
import re
import sys
from pathlib import Path

repo_src = Path(r"G:\FSH\made-in-china\made-in-china\src")
if str(repo_src) not in sys.path:
    sys.path.insert(0, str(repo_src))

from mic_gateway.browser.runtime import BrowserRuntime
from mic_gateway.config import get_settings

TARGET_URL = "https://membercenter.made-in-china.com/message/index.html#inbox/rwKpdOGJfYoM..from=list"
DATA_DIR = Path(r"G:\MadeInChinaGatewayData")

async def main():
    settings = get_settings().model_copy(update={"chromium_headless": False})
    runtime = BrowserRuntime(settings)
    await runtime.start()
    try:
        async def capture(page):
            print(f"Navigating to {TARGET_URL}...")
            await page.goto(TARGET_URL, wait_until="domcontentloaded")
            await page.wait_for_timeout(5000)

            print(f"Current URL: {page.url}")
            print(f"Page Title: {await page.title()}")

            # If login required
            if "login" in page.url or "logon" in page.url:
                print("REDIRECTED_TO_LOGIN")
                return

            # Take screenshot
            screenshot_path = DATA_DIR / "conversation_snapshot.png"
            await page.screenshot(path=str(screenshot_path), full_page=False)
            print(f"Screenshot saved to: {screenshot_path}")

            # Save HTML
            html_path = DATA_DIR / "conversation_snapshot.html"
            content = await page.content()
            html_path.write_text(content, encoding="utf-8")
            print(f"HTML saved to: {html_path} (length: {len(content)})")

            # Inspect elements
            print("\n=== SCANNING ELEMENTS ===")
            
            # 1. Frames
            print(f"\n--- Total Frames: {len(page.frames)} ---")
            for idx, f in enumerate(page.frames):
                print(f"Frame {idx}: name='{f.name}', url='{f.url}'")
                try:
                    tas = f.locator("textarea, [contenteditable='true']")
                    c = await tas.count()
                    if c > 0:
                        print(f"  Frame {idx} has {c} inputs/contenteditables:")
                        for i in range(c):
                            el = tas.nth(i)
                            print(f"    [{i}] tag={await el.evaluate('el => el.tagName')}, class='{await el.get_attribute('class')}', placeholder='{await el.get_attribute('placeholder')}', visible={await el.is_visible()}")
                    
                    btns = f.locator("button, a, div, span, input[type='button']").filter(has_text=re.compile(r"(发送|Send|回复)"))
                    bc = await btns.count()
                    if bc > 0:
                        print(f"  Frame {idx} has {bc} send/reply buttons:")
                        for i in range(bc):
                            b = btns.nth(i)
                            print(f"    [{i}] tag={await b.evaluate('el => el.tagName')}, class='{await b.get_attribute('class')}', text='{(await b.inner_text()).strip()}', visible={await b.is_visible()}")
                except Exception as e:
                    print(f"  Frame {idx} query error: {e}")

            # 2. Main page inputs
            print("\n--- Main Page Inputs/Textareas ---")
            inputs = page.locator("textarea, [contenteditable='true']")
            ic = await inputs.count()
            print(f"Count: {ic}")
            for i in range(ic):
                el = inputs.nth(i)
                box = await el.bounding_box()
                print(f"  Input {i}: tag={await el.evaluate('el => el.tagName')}, class='{await el.get_attribute('class')}', id='{await el.get_attribute('id')}', placeholder='{await el.get_attribute('placeholder')}', visible={await el.is_visible()}, box={box}")

            # 3. Main page Send buttons
            print("\n--- Main Page Send Buttons ---")
            sends = page.locator("button, a, div, span, input[type='button'], input[type='submit']").filter(
                has_text=re.compile(r"(发送|Send)")
            )
            sc = await sends.count()
            print(f"Count: {sc}")
            for i in range(sc):
                b = sends.nth(i)
                box = await b.bounding_box()
                print(f"  Send {i}: tag={await b.evaluate('el => el.tagName')}, class='{await b.get_attribute('class')}', id='{await b.get_attribute('id')}', text='{(await b.inner_text()).strip()}', visible={await b.is_visible()}, box={box}")

            # 4. Check all elements at the bottom of the page (y > 500)
            print("\n--- Elements with text '发送' or '回复' near bottom ---")
            bottom_els = page.locator("button, a, .btn").filter(has_text=re.compile(r"(发送|回复)"))
            for i in range(await bottom_els.count()):
                b = bottom_els.nth(i)
                box = await b.bounding_box()
                print(f"  Bottom {i}: tag={await b.evaluate('el => el.tagName')}, class='{await b.get_attribute('class')}', text='{(await b.inner_text()).strip()}', visible={await b.is_visible()}, box={box}")

        await runtime.run_serialized(capture)
    finally:
        await runtime.stop()

if __name__ == "__main__":
    asyncio.run(main())
