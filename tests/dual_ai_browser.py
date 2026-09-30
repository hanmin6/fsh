"""Independent live-component browser acceptance with an isolated fictional HostBridge.

No provider/CRM connections. Run Vite on loopback port 5176 first.
python3 tests/dual_ai_browser.py
"""
import base64
import os
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'test-results' / 'dual-ai'
OUT.mkdir(parents=True, exist_ok=True)
PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=')
HTML = '''<!doctype html><html lang="zh-CN"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Fictional AI acceptance</title></head><body style="margin:0"><div id="workspace"></div><script type="module">
import {mount} from '/src/main.tsx';
const getDb=()=>JSON.parse(sessionStorage.getItem('acceptance-fictional-db')||'{"plans":{},"jobs":{},"assets":{},"planCalls":0,"jobCalls":0}');
const save=d=>sessionStorage.setItem('acceptance-fictional-db',JSON.stringify(d));
const status={recoverAllowed:true,text:{available:true,defaultChoice:'gpt',models:[{choice:'gpt',label:'GPT-6.1 Sol',available:true},{choice:'grok',label:'Grok 4.7',available:true},{choice:'gemini',label:'Gemini 3.8 Flash',available:false}]},media:{configured:true,enabled:true,videoModel:'minimax-h3-max',capabilities:{image:false,video:true}}};
const source={user:{id:'fictional-acceptance-user',name:'验收测试账号'},can:()=>true,native:()=>{},
 async get(path){const d=getDb();if(path==='Fusanhe/creative/status'){if(sessionStorage.getItem('acceptance-status-error'))throw Error('fixture status error');if(sessionStorage.getItem('acceptance-partial-models'))return {...status,text:{...status.text,available:false,models:status.text.models.map(m=>({...m,available:m.choice==='grok'}))}};return status;}
  if(path==='Fusanhe/media/jobs')return {list:Object.values(d.jobs),total:Object.keys(d.jobs).length};
  if(path==='Fusanhe/creative/assets')return {list:Object.values(d.assets),total:Object.keys(d.assets).length};
  if(path.startsWith('Fusanhe/creative/asset/'))return {dataUrl:'data:video/mp4;base64,AAAAHGZ0eXBpc29tAAAAAGlzb21pc28y',mime:'video/mp4'};
  return {list:[],total:0};},
 async post(path,payload){const d=getDb();
  if(path==='Fusanhe/creative/source')return {id:'fictional-source-1'};
  if(path==='Fusanhe/creative/plan'){if(sessionStorage.getItem('acceptance-plan-error'))throw Error('fixture planning error');
   if(d.plans[payload.idempotencyKey])return d.plans[payload.idempotencyKey];d.planCalls++;
   const plan={...payload,id:'fictional-plan-1',provider:'apimonth',model:payload.modelChoice==='grok'?'grok-4.7':'gpt-6.1-sol',usageTokens:42,planningUsesImage:false,preferences:{purpose:payload.purpose,language:payload.language,aspect:payload.aspect,duration:payload.duration},plans:[{name:'白色台面展示',description:'参考文字构想，将包装陈列在白色台面上。',motion:'镜头缓慢横移，保持背景整洁。',use:'产品介绍'},{name:'厨房使用场景',description:'以简洁厨房场景表达产品用途。',motion:'镜头从环境逐步靠近包装。',use:'客户沟通'},{name:'包装细节特写',description:'画面集中展示包装与陈列细节，事实待人工核对。',motion:'稳定特写，柔和自然光。',use:'社交宣传'}]};d.plans[payload.idempotencyKey]=plan;save(d);return plan;}
  if(path==='Fusanhe/media/jobs'){const old=Object.values(d.jobs).find(j=>j.requestKey===payload.idempotencyKey);if(old)return old;d.jobCalls++;
   const plan=Object.values(d.plans).find(p=>p.id===payload.planId);const job={id:'fictional-job-1',requestKey:payload.idempotencyKey,name:plan.plans[payload.choice].name,kind:'video',status:sessionStorage.getItem('acceptance-uncertain')?'reconcile_required':'queued',sourceId:plan.sourceId,selectedPlan:plan.plans[payload.choice],preferences:plan.preferences,resultId:null,createdAt:'2026-09-30 01:00:00',model:'minimax-h3-max',errorCode:null,sourceMode:payload.sourceUrl?'public_image':'text_only'};d.jobs[job.id]=job;save(d);return job;}
  if(path.endsWith('/reconcile')){const id=path.split('/')[3],job=d.jobs[id];job.status='completed';job.resultId='fictional-asset-1';d.assets[job.resultId]={id:job.resultId,name:job.name,kind:'video',mime:'video/mp4',size:12345,version:1,createdAt:job.createdAt};save(d);return job;}
  if(path.endsWith('/recover'))return d.jobs['fictional-job-1'];
  throw Error('Unexpected fixture mutation '+path);},async patch(){throw Error('No generic mutation');}};
mount(document.getElementById('workspace'),source);
</script></body></html>'''


def no_overflow(page):
    assert not page.evaluate('document.querySelector(".w-main").scrollWidth > document.querySelector(".w-main").clientWidth'), 'horizontal content overflow'


with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=os.getenv('BROWSER_EXECUTABLE') or
        ('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' if Path('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome').exists() else None), headless=True)
    page = browser.new_page(viewport={'width': 1440, 'height': 1100})
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.route('**/acceptance-fixture.html*', lambda r: r.fulfill(body=HTML, content_type='text/html'))
    page.route('**/client/custom/res/fusanhe/logo-full.png', lambda r: r.fulfill(path=str(ROOT/'client/custom/res/fusanhe/logo-full.png'), content_type='image/png'))
    url = 'http://127.0.0.1:5176/acceptance-fixture.html?preview=0&workspace=ai'
    page.goto(url)
    expect(page.get_by_text('图片生成暂未启用', exact=True)).to_be_visible()
    expect(page.get_by_role('button', name='上传并推荐视频方案')).to_be_disabled()
    expect(page.get_by_role('combobox', name='方案模型')).to_have_value('gpt')
    expect(page.get_by_role('combobox', name='方案模型').locator('option[value="gemini"]')).to_have_attribute('disabled', '')
    page.get_by_role('textbox', name='大概想法').fill('展示虚构商品包装，白色台面，柔和自然光。')
    page.get_by_label('上传商品图片', exact=True).set_input_files({'name': 'fictional.png', 'mimeType': 'image/png', 'buffer': PNG})
    page.get_by_role('button', name='上传并推荐视频方案').click()
    expect(page.get_by_role('group', name='选择视频方案')).to_be_visible()
    expect(page.get_by_text('依据文字生成 · gpt-6.1-sol · 42 Token · 未分析图片')).to_be_visible()
    page.get_by_role('button', name='方案 1', exact=False).click()
    page.get_by_role('combobox', name='视频输入').select_option('public_image')
    page.get_by_role('textbox', name='公开商品图片 URL').fill('https://fictional.example/product.png')
    expect(page.get_by_role('button', name='确认并生成视频')).to_be_disabled()
    page.get_by_role('checkbox', name='我有权使用此公开图片').check()
    expect(page.get_by_role('button', name='确认并生成视频')).to_be_enabled()
    page.get_by_role('textbox', name='公开商品图片 URL').fill('https://fictional.example/product-2.png')
    expect(page.get_by_role('checkbox', name='我有权使用此公开图片')).not_to_be_checked()
    expect(page.get_by_role('button', name='确认并生成视频')).to_be_disabled()
    page.get_by_role('combobox', name='视频输入').select_option('text_only')
    no_overflow(page)
    page.evaluate('document.querySelector(".w-main").scrollTop=0')
    page.screenshot(path=str(OUT/'creative-desktop-plans.png'), full_page=True)
    page.set_viewport_size({'width': 390, 'height': 844})
    no_overflow(page)
    page.screenshot(path=str(OUT/'creative-mobile-input.png'), full_page=True)
    page.get_by_role('group', name='选择视频方案').scroll_into_view_if_needed()
    page.screenshot(path=str(OUT/'creative-mobile-plans.png'), full_page=True)
    page.get_by_role('combobox', name='时长').select_option('10')
    expect(page.get_by_text('素材或创作偏好已改变，请重新推荐后生成。')).to_be_visible()
    expect(page.get_by_role('button', name='确认并生成视频')).to_be_disabled()
    page.get_by_role('combobox', name='时长').select_option('5')
    page.get_by_role('button', name='确认并生成视频').click()
    expect(page.locator('.v-job h3')).to_have_text('排队中')
    expect(page.get_by_text('后台持续核对状态，不会自动重复提交。')).to_be_visible()
    page.screenshot(path=str(OUT/'creative-mobile-queued.png'), full_page=True)
    # Refresh loses local component memory; fixture persistence and stable request key remain.
    page.reload()
    page.locator('.w-page-tabs').get_by_role('button', name='创作任务', exact=True).click()
    expect(page.get_by_text('排队中', exact=True)).to_be_visible()
    page.screenshot(path=str(OUT/'creative-mobile-tasks.png'), full_page=True)
    page.locator('.w-page-tabs').get_by_role('button', name='开始创作', exact=True).click()
    page.get_by_role('textbox', name='大概想法').fill('展示虚构商品包装，白色台面，柔和自然光。')
    page.get_by_label('上传商品图片', exact=True).set_input_files({'name': 'fictional.png', 'mimeType': 'image/png', 'buffer': PNG})
    page.get_by_role('button', name='上传并推荐视频方案').click()
    page.get_by_role('button', name='方案 1', exact=False).click()
    page.get_by_role('button', name='确认并生成视频').click()
    expect(page.locator('.v-job h3')).to_have_text('排队中')
    counts = page.evaluate('(()=>{const d=JSON.parse(sessionStorage.getItem("acceptance-fictional-db"));return [d.planCalls,d.jobCalls]})()')
    assert counts == [1, 1], counts
    page.get_by_role('button', name='核对任务状态').click()
    expect(page.locator('.v-job h3')).to_have_text('已完成')
    page.get_by_role('button', name='预览 / 下载作品').click()
    expect(page.get_by_role('dialog').get_by_role('link', name='下载作品')).to_have_attribute('download', '白色台面展示.mp4')
    assert page.get_by_role('dialog').locator('video').get_attribute('src').startswith('data:video/mp4;base64,')
    page.screenshot(path=str(OUT/'creative-mobile-download.png'), full_page=True)
    page.get_by_role('button', name='关闭弹窗').click()
    page.set_viewport_size({'width': 1440, 'height': 1000})
    page.locator('.w-page-tabs').get_by_role('button', name='我的作品', exact=True).click()
    expect(page.get_by_text('版本 1 · 0.0 MB')).to_be_visible()
    page.screenshot(path=str(OUT/'creative-desktop-assets.png'), full_page=True)
    # Terminal rejection must not claim a still-running background process.
    page.evaluate('(()=>{const d=JSON.parse(sessionStorage.getItem("acceptance-fictional-db"));d.jobs["fictional-job-1"].status="failed";d.jobs["fictional-job-1"].resultId=null;sessionStorage.setItem("acceptance-fictional-db",JSON.stringify(d))})()')
    page.goto(url + '&tab=tasks')
    page.locator('.v-history').click()
    expect(page.locator('.v-job h3')).to_have_text('生成失败')
    expect(page.get_by_text('后台持续核对状态，不会自动重复提交。')).to_have_count(0)
    page.screenshot(path=str(OUT/'creative-desktop-failed.png'), full_page=True)
    page.evaluate('(()=>{const d=JSON.parse(sessionStorage.getItem("acceptance-fictional-db"));d.jobs["fictional-job-1"].status="reconcile_required";sessionStorage.setItem("acceptance-fictional-db",JSON.stringify(d))})()')
    page.goto(url + '&tab=tasks')
    page.locator('.v-history').click()
    expect(page.get_by_text('提交结果不明确。请核对供应商后台任务，不要创建重复付费任务。')).to_be_visible()
    expect(page.get_by_role('button', name='恢复任务编号')).to_be_disabled()
    page.screenshot(path=str(OUT/'creative-desktop-uncertain.png'), full_page=True)
    page.evaluate('sessionStorage.setItem("acceptance-status-error","1")')
    page.goto(url)
    expect(page.get_by_role('alert')).to_have_text('创作服务状态加载失败。请联系维护人员或稍后重试。')
    expect(page.get_by_role('button', name='上传并推荐视频方案')).to_be_disabled()
    page.screenshot(path=str(OUT/'creative-desktop-status-error.png'), full_page=True)
    page.set_viewport_size({'width': 390, 'height': 844})
    no_overflow(page)
    page.screenshot(path=str(OUT/'creative-mobile-status-error.png'), full_page=True)
    # A missing default never substitutes a model. Explicitly selecting an available model must work.
    page.evaluate('sessionStorage.removeItem("acceptance-status-error");sessionStorage.setItem("acceptance-partial-models","1")')
    page.goto(url)
    page.get_by_role('textbox', name='大概想法').fill('使用已配置的模型检查虚构产品描述。')
    page.get_by_label('上传商品图片', exact=True).set_input_files({'name': 'fictional.png', 'mimeType': 'image/png', 'buffer': PNG})
    expect(page.get_by_role('img', name='已选择的商品图片')).to_be_visible()
    expect(page.get_by_role('combobox', name='方案模型')).to_have_value('gpt')
    expect(page.get_by_role('button', name='上传并推荐视频方案')).to_be_disabled()
    page.get_by_role('combobox', name='方案模型').select_option('grok')
    expect(page.get_by_role('button', name='上传并推荐视频方案')).to_be_enabled()
    page.get_by_role('button', name='上传并推荐视频方案').click()
    expect(page.get_by_text('依据文字生成 · grok-4.7 · 42 Token · 未分析图片')).to_be_visible()
    page.get_by_role('group', name='选择视频方案').scroll_into_view_if_needed()
    page.screenshot(path=str(OUT/'creative-mobile-explicit-model.png'), full_page=True)
    assert not errors, errors
    browser.close()
print('PASS: isolated live component, model availability, source consent/reset, stale plan gate, refresh idempotency, task persistence, private download, terminal/uncertain/status errors, desktop/mobile overflow')
