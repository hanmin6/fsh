import asyncio
import re
import sys
from pathlib import Path

repo_src = Path(r"G:\FSH\made-in-china\made-in-china\src")
if str(repo_src) not in sys.path:
    sys.path.insert(0, str(repo_src))

from mic_gateway.browser.runtime import BrowserRuntime
from mic_gateway.config import get_settings

TARGET_SOURCE_ID = "rwKpdOGJfYoM"
DATA_DIR = Path(r"G:\MadeInChinaGatewayData")

async def main():
    settings = get_settings().model_copy(update={"chromium_headless": False})
    runtime = BrowserRuntime(settings)
    await runtime.start()
    try:
        async def run(page):
            print("Navigating to message index...")
            await page.goto("https://membercenter.made-in-china.com/message/index.html", wait_until="domcontentloaded")
            await page.wait_for_timeout(3000)

            # Wait for login if needed
            waited = 0
            while ("login" in page.url or "logon" in page.url) and waited < 180:
                if waited % 10 == 0:
                    print(f"Waiting for login in browser... ({waited}s / 180s)")
                await asyncio.sleep(2)
                waited += 2

            if "login" in page.url or "logon" in page.url:
                print("TIMEOUT_WAITING_FOR_LOGIN")
                return

            print(f"Logged in successfully! Current URL: {page.url}")
            await page.wait_for_timeout(2000)

            # Click or navigate to target conversation
            conv_url = f"https://membercenter.made-in-china.com/message/index.html#inbox/{TARGET_SOURCE_ID}..from=list"
            print(f"Navigating to conversation URL: {conv_url}")
            await page.goto(conv_url, wait_until="domcontentloaded")
            await page.wait_for_timeout(4000)

            # If that didn't open the detail, also try clicking row/link
            row_input = page.locator(f"input#{TARGET_SOURCE_ID}")
            if await row_input.count() > 0:
                row = row_input.locator("xpath=ancestor::tr[contains(@class, 'J-inquiry-item') or 1]")
                link = row.locator("a.inquiry-content-go-bomDetail")
                if await link.count() > 0:
                    print("Also triggering click on bom_link...")
                    await link.first.click()
                    await page.wait_for_timeout(3000)

            # Snapshot 1: initial conversation view
            snap1_img = DATA_DIR / "snap_1_conv.png"
            snap1_html = DATA_DIR / "snap_1_conv.html"
            await page.screenshot(path=str(snap1_img))
            snap1_html.write_text(await page.content(), encoding="utf-8")
            print(f"Snapshot 1 saved: {snap1_img}")

            # Check for reply button and click if exists
            reply_btn = page.locator(".btn-reply, button:has-text('回复'), a:has-text('回复')")
            if await reply_btn.count() > 0 and await reply_btn.first.is_visible():
                print("Found reply button, clicking it to expand composer...")
                await reply_btn.first.click()
                await page.wait_for_timeout(3000)

            # Snapshot 2: after reply clicked
            snap2_img = DATA_DIR / "snap_2_after_reply.png"
            snap2_html = DATA_DIR / "snap_2_after_reply.html"
            await page.screenshot(path=str(snap2_img))
            snap2_html.write_text(await page.content(), encoding="utf-8")
            print(f"Snapshot 2 saved: {snap2_img}")

            # Scan DOM
            print("\n=== DOM SCAN RESULTS ===")
            print(f"Page URL: {page.url}")
            print(f"Frames count: {len(page.frames)}")
            for idx, frame in enumerate(page.frames):
                print(f"\n--- Frame {idx}: name='{frame.name}', url='{frame.url}' ---")
                try:
                    tas = frame.locator("textarea, [contenteditable='true'], input[type='text']")
                    tc = await tas.count()
                    print(f"  Inputs count: {tc}")
                    for i in range(tc):
                        el = tas.nth(i)
                        tag = await el.evaluate("el => el.tagName")
                        cls = await el.get_attribute("class")
                        name = await el.get_attribute("name")
                        pid = await el.get_attribute("id")
                        vis = await el.is_visible()
                        box = await el.bounding_box()
                        print(f"    Input [{i}]: tag={tag}, id='{pid}', name='{name}', class='{cls}', visible={vis}, box={box}")

                    btns = frame.locator("button, a, div, span, input[type='button'], input[type='submit']").filter(
                        has_text=re.compile(r"(发送|Send|回复)")
                    )
                    bc = await btns.count()
                    print(f"  Buttons (发送/回复/Send) count: {bc}")
                    for i in range(bc):
                        b = btns.nth(i)
                        tag = await b.evaluate("el => el.tagName")
                        cls = await b.get_attribute("class")
                        txt = (await b.inner_text()).strip()
                        vis = await b.is_visible()
                        box = await b.bounding_box()
                        print(f"    Button [{i}]: tag={tag}, class='{cls}', text='{txt}', visible={vis}, box={box}")
                except Exception as e:
                    print(f"  Frame {idx} scan error: {e}")

            print("\nSNAPSHOT_COMPLETED", flush=True)
            await asyncio.sleep(2)

        await runtime.run_serialized(run)
    finally:
        await runtime.stop()

if __name__ == "__main__":
    asyncio.run(main())

