import os
from playwright.sync_api import sync_playwright
from pathlib import Path

def verify():
 with sync_playwright() as p:
  browser=p.chromium.launch(executable_path=os.getenv('BROWSER_EXECUTABLE') or ('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' if Path('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome').exists() else None),headless=True)
  page=browser.new_page(viewport={'width':1440,'height':1000});errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  page.goto('http://127.0.0.1:5176/tests/product-creative.html')
  page.get_by_role('button',name='蓝莓（测试产品）').click()
  page.get_by_role('button',name='生成推荐方案').click()
  page.get_by_role('button',name='产品展示 质感特写').click()
  page.get_by_label('画面描述').fill('已修改的产品近景')
  page.screenshot(path='/tmp/product-creative-desktop.png',full_page=True)
  page.get_by_role('button',name='生成视频',exact=True).click()
  page.locator('.v-job h3').filter(has_text='排队中').wait_for()
  calls=page.evaluate('window.submissions');jobs=[c for c in calls if c['path']=='Fusanhe/media/jobs']
  assert len(jobs)==1 and jobs[0]['data']['useSourceImage'] is True
  assert jobs[0]['data']['selectedPlan']['description']=='已修改的产品近景'
  assert '/private/' not in next(c['data']['idea'] for c in calls if c['path'].endswith('/plan'))
  page.get_by_role('button',name='我的作品',exact=True).click()
  page.get_by_role('button',name='已有视频作品').click()
  page.get_by_role('dialog',name='已有视频作品').wait_for()
  page.get_by_role('button',name='关闭弹窗').click()
  page.get_by_role('button',name='创作任务',exact=True).click()
  page.get_by_role('button',name='历史草莓方案').click()
  page.locator('.v-job-preview img').wait_for()
  assert page.locator('.v-job-preview img').get_attribute('src').endswith('#history-source'),'History uses its own saved source'
  assert page.locator('.v-input h2').inner_text()=='草莓（测试产品）'
  assert page.get_by_label('上传产品首帧').count()==0,'Saved job source cannot be edited'
  page.get_by_role('button',name='创作任务',exact=True).click()
  page.evaluate('window.completeHistory()')
  page.get_by_role('button',name='刷新',exact=True).click()
  page.get_by_role('button',name='历史草莓方案').click()
  page.get_by_role('button',name='查看首帧',exact=True).click()
  page.get_by_role('dialog',name='产品首帧').wait_for()
  page.wait_for_timeout(700)
  assert page.get_by_role('dialog',name='产品首帧').locator('img').count()==1,'Auto video responses do not overwrite manual source previews'
  page.get_by_role('button',name='关闭弹窗').click()
  page.get_by_role('button',name='创作任务',exact=True).click()
  page.evaluate('window.historyDelay=true')
  page.get_by_role('button',name='历史草莓方案').click()
  page.get_by_role('button',name='换产品',exact=True).click()
  page.get_by_role('button',name='蓝莓（测试产品）').click()
  page.wait_for_timeout(700)
  assert page.locator('.v-input h2').inner_text()=='蓝莓（测试产品）','Late history responses do not replace a new product'
  page.get_by_role('button',name='换产品',exact=True).click()
  page.get_by_role('button',name='草莓（测试产品）').click()
  assert page.get_by_role('button',name='生成推荐方案').is_disabled(),'Candidates require explicit selection'
  page.get_by_role('button',name='使用图片 产品首帧').click()
  page.get_by_role('button',name='生成推荐方案').click()
  page.get_by_role('button',name='产品展示 质感特写').click()
  page.get_by_role('textbox',name='补充要求').fill('修改要求')
  assert page.get_by_role('button',name='生成视频',exact=True).is_disabled(),'Stale plans cannot submit'
  page.set_viewport_size({'width':390,'height':844})
  assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'),'No mobile horizontal overflow'
  page.screenshot(path='/tmp/product-creative-mobile.png',full_page=True)
  page.get_by_role('button',name='换产品',exact=True).click()
  page.evaluate('window.productFailure=true')
  page.get_by_role('button',name='蓝莓（测试产品）').click()
  page.get_by_role('alert').wait_for()
  assert not errors,errors
  print('Product-first UI passed: selection, candidate confirmation, plan edits, source transfer, stale blocking, assets preview, historical source, navigation races, failure state, responsive layout')
  browser.close()
if __name__=='__main__':verify()
