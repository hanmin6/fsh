import os
"""Global customer rating order must precede filtering and pagination."""
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

ROOT=Path(__file__).resolve().parents[1]
URL='http://127.0.0.1:5176/tests/conversation-profile.html?workspace=messages&sorting=1'
OUT=ROOT/'test-results/conversation-sort'
OUT.mkdir(parents=True,exist_ok=True)
expect.set_options(timeout=10000)
with sync_playwright() as p:
    browser=p.chromium.launch(executable_path=os.getenv('BROWSER_EXECUTABLE') or ('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' if Path('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome').exists() else None),headless=True)
    page=browser.new_page(viewport={'width':1440,'height':1000})
    errors=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.route('**/client/custom/res/fusanhe/logo-full.png',lambda r:r.fulfill(path=str(ROOT/'client/custom/res/fusanhe/logo-full.png')))
    page.goto(URL)
    order=page.get_by_role('combobox',name='会话排序',exact=True)
    expect(order).to_have_value('rating')
    rows=page.locator('.w-conversation-list .w-conversation')
    expect(rows).to_have_count(30)
    expect(rows.nth(0)).to_contain_text('Sort Top Newer')
    expect(rows.nth(1)).to_contain_text('Sort Top Older')
    expect(rows.nth(2)).to_contain_text('Sort High')
    expect(rows.nth(29).locator('.w-badge').first).to_have_text('中')
    expect(page.locator('.w-paging')).to_contain_text('共 127 条')
    page.screenshot(path=str(OUT/'desktop.png'),full_page=True)
    for i in range(4):
        page.get_by_role('button',name='下一页',exact=True).click()
        expect(page.locator('.w-paging')).to_contain_text('第 '+str(i+2)+' 页')
    expect(rows).to_have_count(7)
    expect(rows.nth(3).locator('.w-badge').first).to_have_text('低')
    expect(rows.nth(4).locator('.w-badge').first).to_have_text('超低')
    expect(rows.nth(5)).to_contain_text('Sort Unlinked')
    expect(rows.nth(6)).to_contain_text('Sort Pending')
    order.select_option('latest')
    expect(page.locator('.w-paging')).to_contain_text('第 1 页')
    expect(rows.nth(0)).to_contain_text('Sort Unlinked')
    expect(rows.nth(1)).to_contain_text('Sort Pending')
    order.select_option('rating')
    expect(rows.nth(0)).to_contain_text('Sort Top Newer')
    search=page.get_by_role('textbox',name='搜索客户或会话',exact=True)
    search.fill('Sort Top')
    expect(rows).to_have_count(2)
    expect(rows.nth(0)).to_contain_text('Sort Top Newer')
    search.fill('')
    platform=page.get_by_role('combobox',name='消息来源渠道',exact=True)
    platform.select_option('mic')
    expect(rows.nth(0)).to_contain_text('Sort Top Older')
    expect(page.locator('.w-paging')).to_contain_text('共 61 条')
    platform.select_option('')
    page.get_by_role('button',name='未读',exact=True).click()
    expect(rows.nth(0)).to_contain_text('Sort Top Newer')
    expect(page.locator('.w-paging')).to_contain_text('共 67 条')
    page.get_by_role('button',name='全部',exact=True).click()
    order.select_option('latest')
    page.reload()
    expect(order).to_have_value('latest')
    page.set_viewport_size({'width':390,'height':844})
    expect(order).to_be_visible()
    order.select_option('rating')
    expect(rows.nth(0)).to_contain_text('Sort Top Newer')
    assert not page.evaluate('document.querySelector(".w-main").scrollWidth > document.querySelector(".w-main").clientWidth')
    page.screenshot(path=str(OUT/'mobile.png'),full_page=True)
    assert page.evaluate('window.fixtureWrites')==[]
    assert not errors,errors
    browser.close()
print('PASS: global grade sorting over 127 conversations, same-grade timestamps, pagination, search, platform, unread, persistence and mobile')
