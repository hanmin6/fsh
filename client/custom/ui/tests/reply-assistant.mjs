/** Full browser contract checks against a synthetic host; no real customer data. */
import {chromium,expect} from '@playwright/test';
import {createServer} from 'node:http';
import {readFile,mkdir,writeFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
const root=fileURLToPath(new URL('../../../../',import.meta.url));
const output=path.join(root,'runtime/reply-assistant');await mkdir(output,{recursive:true});
const requests=[];let failure=0,slow=0;
const analysis={recognizedText:'Customer: Your price is higher than another supplier. Can you offer a better price?',summaryZh:'客户正在比较供应商，认为报价偏高，希望获得更优惠的价格。',language:'en',directions:[{id:'direction-1',title:'先了解采购条件',description:'询问采购数量、包装和目的港，再评估报价空间。'},{id:'direction-2',title:'核对报价差异',description:'核对规格与贸易条款，帮助客户比较报价。'},{id:'direction-3',title:'探讨替代方案',description:'了解预算和用途，再讨论合适的规格或包装。'}],warnings:[]};
const html=`<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>福三和 · 合成数据交互验证</title><link rel="stylesheet" href="/client/custom/res/workspace/workspace.css"><body><div id="root"></div><script src="/client/custom/res/workspace/workspace.js"></script><script>
async function request(method,p,data){const r=await fetch('/api/'+p,{method,headers:{'Content-Type':'application/json'},body:method==='GET'?undefined:JSON.stringify(data)});if(!r.ok)throw {status:r.status};return r.json()}
FusanheWorkspace.mount(document.getElementById('root'),{get:(p)=>request('GET',p),post:(p,d)=>request('POST',p,d),patch:(p,d)=>request('PATCH',p,d),can:()=>!new URLSearchParams(location.search).has('denied'),native:()=>{},user:{id:'synthetic',name:'合成数据验证'}});
</script></body></html>`;
const server=createServer(async(req,res)=>{try{
 const url=new URL(req.url,'http://localhost');
 if(url.pathname==='/'){res.setHeader('Content-Type','text/html; charset=utf-8');res.end(html);return}
 if(url.pathname.startsWith('/api/')){
  if(process.argv.includes('--serve')){res.statusCode=503;res.setHeader('Content-Type','application/json');res.end(JSON.stringify({error:'preview_only'}));return}
  let data='';for await(const chunk of req)data+=chunk;
  const p=data?JSON.parse(data):{};requests.push({path:url.pathname,body:p});
  if(slow)await new Promise(resolve=>setTimeout(resolve,slow));
  res.setHeader('Content-Type','application/json');
  if(failure){res.statusCode=failure;res.end('{}');return}
  if(url.pathname.endsWith('reply-assistant')){
   const result=p.operation==='analyze'?analysis:{draftText:p.refinement?'Could you share the order quantity and destination port?':'Thank you for your feedback. Could you share your expected order quantity, packaging requirements and destination port? We will review your requirements before preparing a proposal.',translationZh:p.refinement?'请问您的采购数量和目的港是什么？':'感谢您的反馈。方便告知预计采购量、包装要求和目的港吗？我们会先评估您的需求，再准备方案。',missingInformation:['采购数量、包装要求和目的港待确认。'],conflictNote:p.customInstruction.includes('冲突')?'自定义要求与所选方向不同，已优先按你的要求起草。':''};
   res.end(JSON.stringify({ok:true,result}));return;
  }
  if(url.pathname.endsWith('manual-draft')){res.end(JSON.stringify({draftId:'synthetic-draft'}));return}
  if(url.pathname.endsWith('ExternalConversation/demo-conversation')){res.end(JSON.stringify({id:'demo-conversation',name:'示例采购商'}));return}
  res.end(JSON.stringify({list:[{id:'m1',direction:'inbound',body:'Can you quote for 500 kg?',sentAt:'2026-10-15 01:00:00'}],total:1}));return;
 }
 const assets={'/client/custom/res/workspace/workspace.js':'text/javascript','/client/custom/res/workspace/workspace.css':'text/css','/client/custom/res/fusanhe/logo-full.png':'image/png'};
 if(!assets[url.pathname]){res.statusCode=404;res.end();return}
 res.setHeader('Content-Type',assets[url.pathname]);res.end(await readFile(path.join(root,url.pathname)));
}catch(e){res.statusCode=500;res.end('Synthetic host failure')}});
await new Promise(resolve=>server.listen(process.argv.includes('--serve')?4175:0,'127.0.0.1',resolve));
const base=`http://127.0.0.1:${server.address().port}`;
if(process.argv.includes('--serve')){console.log(`Synthetic preview: ${base}/?workspace=reply&preview=1`);await new Promise(()=>{});}
const browser=await chromium.launch({channel:process.env.BROWSER_CHANNEL||undefined,headless:true});
const page=await browser.newPage({viewport:{width:1440,height:1000}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
try{
 await page.setContent('<html lang="en"><body style="font:24px Arial;padding:32px;width:560px;background:#fafafa"><h2>Synthetic chat for testing</h2><p>Customer: Your price is higher than another supplier. Can you offer a better price?</p></body></html>');
 const png=await page.screenshot();await writeFile(path.join(output,'synthetic-chat.png'),png);
 await page.goto(base+'/?workspace=reply');
 await expect(page.getByRole('heading',{name:'AI 帮我回复',exact:true})).toBeVisible();
 await expect(page.getByRole('button',{name:'按这个思路生成回复'})).toBeDisabled();
 await page.getByLabel('上传聊天截图').setInputFiles({name:'chat.png',mimeType:'image/png',buffer:png});
 await expect(page.getByRole('button',{name:'查看截图 1'})).toBeVisible();
 slow=100;await page.getByRole('button',{name:'分析回复方向',exact:true}).click();
 await expect(page.getByRole('button',{name:'按这个思路生成回复'})).toBeDisabled();
 await expect(page.getByRole('group',{name:'选择回复方向'}).getByRole('button')).toHaveCount(3);slow=0;
 await page.getByRole('button',{name:/先了解采购条件/}).click();
 await page.locator('#ra-custom').fill('先别降价，问采购量，语气客气一点。');
 await page.screenshot({path:path.join(output,'desktop.png'),fullPage:true});
 await page.getByRole('button',{name:'按这个思路生成回复'}).click();
 await expect(page.locator('#ra-draft')).toHaveValue(/Thank you/);
 await page.locator('#ra-draft').fill('Edited reply: Please share the quantity.');
 await expect(page.getByText(/正文已修改，以下为修改前的释义/)).toBeVisible();
 await page.context().grantPermissions(['clipboard-read','clipboard-write']);
 await page.getByRole('button',{name:'复制回复',exact:true}).click();
 if(await page.evaluate(()=>navigator.clipboard.readText())!=='Edited reply: Please share the quantity.')throw Error('copy includes more than body');
 await page.getByRole('button',{name:'简短一点',exact:true}).click();
 await expect(page.locator('#ra-draft')).toHaveValue(/Could you share/);
 const refinement=requests.find(r=>r.body.refinement==='shorter');
 if(refinement.body.currentDraft!=='Edited reply: Please share the quantity.')throw Error('edited draft not forwarded');
 await page.screenshot({path:path.join(output,'desktop-result.png'),fullPage:true});
 await page.getByRole('button',{name:'修改方向'}).click();
 await expect(page.locator('#ra-custom')).toHaveValue('先别降价，问采购量，语气客气一点。');
 await page.getByRole('button',{name:/先了解采购条件/}).click();
 await page.getByRole('button',{name:'按这个思路生成回复'}).click();
 await expect(page.locator('#ra-draft')).toBeVisible();
 const customCall=requests.filter(r=>r.body.operation==='generate').at(-1);if(customCall.body.direction!==null)throw Error('custom-only not supported');
 await page.getByRole('button',{name:'修改方向'}).click();
 await page.locator('#ra-text').fill('Customer: Corrected request.');
 await expect(page.getByRole('group',{name:'选择回复方向'})).toHaveCount(0);
 failure=503;await page.getByRole('button',{name:'按这个思路生成回复'}).click();
 await expect(page.getByRole('alert')).toContainText('尚未配置');await expect(page.locator('#ra-text')).toHaveValue('Customer: Corrected request.');failure=0;
 await page.getByRole('button',{name:'移除截图 1'}).click();await expect(page.locator('#ra-text')).toHaveValue('');
 await page.evaluate(async(encoded)=>{const bytes=Uint8Array.from(atob(encoded),c=>c.charCodeAt(0));const transfer=new DataTransfer();transfer.items.add(new File([bytes],'pasted.png',{type:'image/png'}));document.querySelector('.ra-page').dispatchEvent(new ClipboardEvent('paste',{clipboardData:transfer,bubbles:true,cancelable:true}));},png.toString('base64'));
 await expect(page.getByRole('button',{name:'查看截图 1'})).toBeVisible();
 await page.evaluate(async(encoded)=>{const bytes=Uint8Array.from(atob(encoded),c=>c.charCodeAt(0));const transfer=new DataTransfer();transfer.items.add(new File([bytes],'dropped.png',{type:'image/png'}));document.querySelector('.ra-upload').dispatchEvent(new DragEvent('drop',{dataTransfer:transfer,bubbles:true,cancelable:true}));},png.toString('base64'));
 await expect(page.getByRole('button',{name:'查看截图 2'})).toBeVisible();
 await page.getByLabel('上传聊天截图').setInputFiles({name:'not.svg',mimeType:'image/svg+xml',buffer:Buffer.from('<svg/>')});await expect(page.getByRole('alert')).toContainText('PNG');
 await page.goto(base+'/?workspace=reply&record=demo-conversation');
 await expect(page.locator('#ra-text')).toHaveValue(/500 kg/);await page.locator('#ra-custom').fill('先确认包装');
 await page.getByRole('button',{name:'按这个思路生成回复'}).click();
 await page.getByRole('button',{name:'保存到会话草稿'}).click();await expect(page.getByRole('button',{name:'已保存草稿'})).toBeDisabled();
 if(requests.filter(r=>r.path.endsWith('/manual-draft')).length!==1)throw Error('draft save count');
 await page.goto(base+'/?workspace=reply&denied=1');await expect(page.getByRole('button',{name:'分析回复方向',exact:true})).toBeDisabled();
 const mobile=await browser.newPage({viewport:{width:390,height:844},isMobile:true,deviceScaleFactor:1});
 await mobile.goto(base+'/?workspace=reply&preview=1');await mobile.getByRole('button',{name:'载入示例询盘'}).click();await mobile.getByRole('button',{name:/先了解采购条件/}).click();
 await mobile.evaluate(()=>{document.querySelector('.w-main').scrollTop=0});
 await mobile.screenshot({path:path.join(output,'mobile.png'),fullPage:true});
 await mobile.locator('#ra-custom').scrollIntoViewIfNeeded();
 await mobile.screenshot({path:path.join(output,'mobile-direction.png'),fullPage:true});
 const overflow=await mobile.evaluate(()=>{const main=document.querySelector('.w-main');return main.scrollWidth>main.clientWidth});if(overflow)throw Error('mobile horizontal overflow');
 await mobile.getByRole('button',{name:'按这个思路生成回复'}).click();await expect(mobile.locator('#ra-draft')).toHaveValue(/Thank you/);
 await mobile.locator('.ra-refine').scrollIntoViewIfNeeded();
 await mobile.screenshot({path:path.join(output,'mobile-result.png'),fullPage:true});
 if(errors.length)throw Error(errors.join('\n'));
 console.log('Browser flow passed: upload, directions, custom-only, editing/copy, refinement, invalidation, errors, linked save, permissions, mobile.');
 console.log(`Screenshots: ${output}`);
}finally{await browser.close();server.close();}
