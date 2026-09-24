import asyncio
import sys
from pathlib import Path

repo_src = Path(r"G:\FSH\made-in-china\made-in-china\src")
if str(repo_src) not in sys.path:
    sys.path.insert(0, str(repo_src))

from mic_gateway.browser.runtime import BrowserRuntime
from mic_gateway.config import get_settings

TARGET_SOURCE_ID = "rwKpdOGJfYoM"

async def main():
    settings = get_settings().model_copy(update={"chromium_headless": False})
    runtime = BrowserRuntime(settings)
    await runtime.start()
    try:
        async def diagnose(page):
            print(f"Navigating to message center...")
            await page.goto("https://membercenter.made-in-china.com/message/index.html", wait_until="domcontentloaded")
            await page.wait_for_timeout(3000)

            # Check if login required
            current_url = page.url
            print(f"Current URL: {current_url}")
            if "login" in current_url or "logon" in current_url:
                print("\n>>> 请在弹出的浏览器中登录账号并进入询盘后台...")
                await asyncio.to_thread(input, ">>> 登录完成后，请回到此处按回车键继续: ")
                await page.goto("https://membercenter.made-in-china.com/message/index.html", wait_until="domcontentloaded")
                await page.wait_for_timeout(3000)

            print(f"Current URL after login check: {page.url}")
            
            # Check target conversation row
            row_input = page.locator(f"input#{TARGET_SOURCE_ID}")
            if await row_input.count() == 0:
                print(f"ERROR: Row with id {TARGET_SOURCE_ID} not found on page!")
                rows = page.locator("tr.J-inquiry-item")
                print(f"Total J-inquiry-item rows: {await rows.count()}")
                return

            row = row_input.locator("xpath=ancestor::tr[contains(@class, 'J-inquiry-item')]")
            if await row.count() == 0:
                row = row_input.locator("xpath=ancestor::tr[1]")
            
            print(f"Found target row: {await row.first.get_attribute('class')}")
            
            # Look at links inside row
            bom_link = row.locator("a.inquiry-content-go-bomDetail")
            title_link = row.locator(".J-inquiry-title")
            print(f"bom_link count: {await bom_link.count()}")
            print(f"title_link count: {await title_link.count()}")
            if await bom_link.count() > 0:
                print(f"bom_link href: '{await bom_link.first.get_attribute('href')}'")
                print(f"bom_link data-url: '{await bom_link.first.get_attribute('data-url')}'")

            # Check right panel before click
            wrap = page.locator("#inquiryDetailReactWrap")
            wrap_exists = await wrap.count() > 0
            wrap_visible = await wrap.is_visible() if wrap_exists else False
            print(f"#inquiryDetailReactWrap exists: {wrap_exists}, visible: {wrap_visible}")
            
            # Listen to new pages
            context = page.context
            new_pages = []
            context.on("page", lambda p: new_pages.append(p))

            print("\n--- 尝试点击 bom_link ---")
            await bom_link.first.click()
            print("bom_link clicked, waiting 4s...")
            await page.wait_for_timeout(4000)

            print(f"Context pages: {len(context.pages)}, New pages opened: {len(new_pages)}")
            for idx, p in enumerate(context.pages):
                print(f"  Page {idx}: {p.url} (title: {await p.title()})")

            # Check if active page changed or wrap changed
            active_page = new_pages[0] if new_pages else page
            
            # Dump info about wrap or active page
            wrap_after = active_page.locator("#inquiryDetailReactWrap")
            if await wrap_after.count() > 0 and await wrap_after.is_visible():
                print("\n#inquiryDetailReactWrap on active page is visible!")
                html = await wrap_after.inner_html()
                print(f"Length of wrap HTML: {len(html)}")
                
                # Check for error
                error = active_page.locator("#inquiryDetailReactWrap .init-error")
                print(f".init-error count: {await error.count()}, visible: {await error.is_visible() if await error.count() else False}")
                
                # Check for composer
                textareas = active_page.locator("#inquiryDetailReactWrap textarea")
                print(f"Textareas in wrap: {await textareas.count()}")
                for t_idx in range(await textareas.count()):
                    ta = textareas.nth(t_idx)
                    print(f"  Textarea {t_idx}: class='{await ta.get_attribute('class')}', placeholder='{await ta.get_attribute('placeholder')}', visible={await ta.is_visible()}")

                if await textareas.count() == 0 and await title_link.count() > 0:
                    print("\n--- bom_link 未唤起输入框，尝试点击 title_link (.J-inquiry-title) ---")
                    await title_link.first.click()
                    await page.wait_for_timeout(3000)
                    textareas = active_page.locator("#inquiryDetailReactWrap textarea")
                    print(f"Textareas in wrap after title click: {await textareas.count()}")
                    for t_idx in range(await textareas.count()):
                        ta = textareas.nth(t_idx)
                        print(f"  Textarea {t_idx}: class='{await ta.get_attribute('class')}', placeholder='{await ta.get_attribute('placeholder')}', visible={await ta.is_visible()}")
                
                editables = active_page.locator("#inquiryDetailReactWrap [contenteditable='true']")
                print(f"Contenteditable in wrap: {await editables.count()}")
                for e_idx in range(await editables.count()):
                    ed = editables.nth(e_idx)
                    print(f"  Editable {e_idx}: class='{await ed.get_attribute('class')}', visible={await ed.is_visible()}")

                # Check for buttons
                buttons = active_page.locator("#inquiryDetailReactWrap button")
                print(f"Buttons in wrap: {await buttons.count()}")
                for b_idx in range(await buttons.count()):
                    btn = buttons.nth(b_idx)
                    b_cls = await btn.get_attribute("class")
                    b_txt = (await btn.inner_text()).strip().replace("\n", " ")
                    print(f"  Button {b_idx}: class='{b_cls}', text='{b_txt}', visible={await btn.is_visible()}")
            else:
                print("\n#inquiryDetailReactWrap is NOT visible after click!")
                print(f"Active page URL: {active_page.url}")
                all_textareas = active_page.locator("textarea")
                print(f"All textareas on page: {await all_textareas.count()}")
                for t_idx in range(await all_textareas.count()):
                    ta = all_textareas.nth(t_idx)
                    print(f"  Textarea {t_idx}: class='{await ta.get_attribute('class')}', placeholder='{await ta.get_attribute('placeholder')}', visible={await ta.is_visible()}")

            # If still nothing, let user click manually and observe
            print("\n>>> 如果刚才没有打开会话，请在浏览器中手动点击 Mr. Mireille Sacrifice 会话，然后在此处按回车: ")
            await asyncio.to_thread(input)
            
            # Inspect again after user click
            print("\n--- 检查手动点击后的页面状态 ---")
            for idx, p in enumerate(context.pages):
                print(f"Page {idx}: {p.url} (title: {await p.title()})")
                wrap = p.locator("#inquiryDetailReactWrap")
                if await wrap.count() > 0 and await wrap.is_visible():
                    print(f"  Page {idx} has visible #inquiryDetailReactWrap!")
                    tas = p.locator("#inquiryDetailReactWrap textarea")
                    print(f"    Textareas: {await tas.count()}")
                    for t_idx in range(await tas.count()):
                        ta = tas.nth(t_idx)
                        print(f"      Textarea {t_idx}: class='{await ta.get_attribute('class')}', placeholder='{await ta.get_attribute('placeholder')}', visible={await ta.is_visible()}")
                    btns = p.locator("#inquiryDetailReactWrap button")
                    print(f"    Buttons: {await btns.count()}")
                    for b_i in range(await btns.count()):
                        btn = btns.nth(b_i)
                        print(f"      Button {b_i}: class='{await btn.get_attribute('class')}', text='{(await btn.inner_text()).strip()}'")
                else:
                    all_tas = p.locator("textarea")
                    print(f"  Page {idx} textarea count: {await all_tas.count()}")
                    for t_idx in range(await all_tas.count()):
                        ta = all_tas.nth(t_idx)
                        print(f"    Textarea {t_idx}: class='{await ta.get_attribute('class')}', visible={await ta.is_visible()}")

        await runtime.run_serialized(diagnose)
    finally:
        await runtime.stop()

if __name__ == "__main__":
    asyncio.run(main())

