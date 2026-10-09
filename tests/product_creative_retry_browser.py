from pathlib import Path
import os
from playwright.sync_api import sync_playwright

def verify():
 with sync_playwright() as p:
  browser=p.chromium.launch(executable_path=os.getenv('BROWSER_EXECUTABLE') or ('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' if Path('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome').exists() else None),headless=True)
  page=browser.new_page(viewport={'width':1440,'height':1000})
  page.goto('http://127.0.0.1:5176/tests/product-creative.html')
  page.get_by_role('button',name='蓝莓（测试产品）').click()
  page.get_by_role('button',name='生成推荐方案').click()
  page.get_by_role('button',name='产品展示 质感特写').click()
  page.evaluate('window.rejectVideo=true')
  page.get_by_role('button',name='生成视频',exact=True).click()
  page.locator('.v-job h3').filter(has_text='生成失败').wait_for()
  initial=page.evaluate("window.submissions.filter(c=>c.path==='Fusanhe/media/jobs')[0].data.idempotencyKey")
  page.get_by_role('button',name='换方案再生成',exact=True).click()
  page.evaluate('window.rejectVideo=false;window.videoTimeout=true')
  page.get_by_role('button',name='生成视频',exact=True).click()
  page.get_by_role('alert').wait_for()
  second=page.evaluate("window.submissions.filter(c=>c.path==='Fusanhe/media/jobs')[1].data.idempotencyKey")
  assert initial!=second,'Intentional retry after a definite rejection must create a new request'
  page.evaluate('window.videoTimeout=false')
  page.get_by_role('button',name='生成视频',exact=True).click()
  page.locator('.v-job h3').filter(has_text='排队中').wait_for()
  third=page.evaluate("window.submissions.filter(c=>c.path==='Fusanhe/media/jobs')[2].data.idempotencyKey")
  assert third==second,'Uncertain retry must reuse its request key to prevent duplicate paid submission'
  print('Retry passed: new request after definitive rejection, same request after uncertain timeout')
  browser.close()
if __name__=='__main__':verify()
