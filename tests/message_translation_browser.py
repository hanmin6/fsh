import os
"""Automatic translations preserve originals, work through pagination, and fail independently."""
from pathlib import Path
from playwright.sync_api import sync_playwright, expect
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'test-results/message-translation';OUT.mkdir(parents=True,exist_ok=True)
BASE='http://127.0.0.1:5176/tests/message-translation.html?workspace=messages&record=v1'
expect.set_options(timeout=20000)
with sync_playwright() as p:
 browser=p.chromium.launch(executable_path=os.getenv('BROWSER_EXECUTABLE') or ('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' if Path('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome').exists() else None),headless=True)
 page=browser.new_page(viewport={'width':1536,'height':960});errors=[]
 page.on('pageerror',lambda e:errors.append(str(e)))
 page.route('**/client/custom/res/fusanhe/logo-full.png',lambda r:r.fulfill(path=str(ROOT/'client/custom/res/fusanhe/logo-full.png')))
 page.goto(BASE)
 expect(page.locator('#message-m33 .w-translation')).to_contain_text('请确认包装 33。')
 expect(page.locator('#message-m33 .w-bubble')).to_have_text('Please confirm packaging 33.')
 page.get_by_role('button',name='加载更早消息',exact=True).click()
 expect(page.locator('#message-m2 .w-translation')).to_contain_text('你好，已有译文')
 expect(page.locator('#message-m5 .w-translation')).to_contain_text('1,600 箱')
 expect(page.locator('#message-m5 .w-translation')).to_contain_text('FS-20 和 buyer@example.com')
 expect(page.locator('#message-m6 .w-translation')).to_contain_text('完整规格')
 expect(page.locator('#message-m3')).to_contain_text('翻译失败')
 before=page.evaluate('window.translationCalls.length')
 page.locator('#message-m3').get_by_role('button',name='重试翻译',exact=True).click()
 expect(page.locator('#message-m3 .w-translation')).to_contain_text('请确认包装 3。')
 assert page.evaluate('window.translationCalls.length')==before+1
 calls=page.evaluate('window.translationCalls');ids=[i for c in calls for i in c['messageIds']]
 assert 'm1' not in ids and 'm2' not in ids
 assert all(len(c['messageIds'])<=6 for c in calls)
 assert page.evaluate('window.maxActiveCalls')==1
 assert page.locator('#message-m1 .w-translation').count()==0
 assert page.locator('#message-m4 .w-translation').count()==0
 assert all(ids.count('m'+str(i))==1 for i in range(34) if i not in [1,2,3])
 assert ids.count('m3')==2
 page.screenshot(path=str(OUT/'desktop.png'),full_page=True)
 page.set_viewport_size({'width':390,'height':844})
 page.locator('#message-m5').scroll_into_view_if_needed()
 assert not page.evaluate('document.querySelector(".w-main").scrollWidth > document.querySelector(".w-main").clientWidth')
 page.screenshot(path=str(OUT/'mobile.png'),full_page=True)
 page.set_viewport_size({'width':1536,'height':960})
 # An unresolved request from the previous conversation cannot insert a translation here.
 page.goto(BASE+'&slow=1')
 expect(page.locator('.w-translation-status').first).to_contain_text('正在翻译')
 page.locator('.w-conversation').filter(has_text='Fictional Contact').click()
 expect(page.locator('.w-chat-header')).to_contain_text('Fictional Contact')
 expect(page.locator('.w-timeline .w-message')).to_have_count(0)
 page.wait_for_timeout(1200)
 expect(page.locator('.w-timeline .w-message')).to_have_count(0)
 assert page.evaluate('window.fixtureWrites')==[]
 assert not errors,errors
 browser.close()
print('PASS: automatic Chinese, originals, existing translations, Chinese/non-English skip, long messages, batches, retry, switching, mobile')
