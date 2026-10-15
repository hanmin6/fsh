import {useEffect,useRef,useState} from 'react';
import {ArrowLeft,ArrowRight,Check,Copy,FileText,ImagePlus,MessageSquareReply,RefreshCw,Upload,X} from 'lucide-react';
import type {DataSource} from './bridge';
import type {Route} from './domain';
import type {Navigate} from './main';
import {Button,Dialog,Notice} from './ui';
import {canGenerate,generationPayload,languages,replyError,sampleAnalysis,sampleReply,validateFiles,type Analysis,type Refinement,type ReplyImage,type ReplyResult} from './reply-domain';
import './reply-assistant.css';

type Props={source:DataSource;route:Route;navigate:Navigate;notify:(message:string)=>void};
async function readImage(file:File):Promise<ReplyImage>{
 const dataUrl=await new Promise<string>((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(String(reader.result));reader.onerror=()=>reject(new Error('无法读取图片，请重新选择。'));reader.readAsDataURL(file)});
 const img=new window.Image();img.src=dataUrl;
 try{await img.decode()}catch{throw new Error('这张图片无法读取，请重新导出为 PNG、JPG 或 WebP。')}
 if(img.width>12000||img.height>12000||img.width*img.height>20000000)throw new Error('截图分辨率过大，请裁剪聊天区域后再上传。');
 return {id:crypto.randomUUID(),name:file.name||'粘贴的截图.png',dataUrl,size:file.size};
}
export function ReplyAssistantPage({source,route,navigate,notify}:Props){
 const [images,setImages]=useState<ReplyImage[]>([]),[text,setText]=useState(''),[analysis,setAnalysis]=useState<Analysis|null>(null);
 const [selected,setSelected]=useState(''),[custom,setCustom]=useState(''),[language,setLanguage]=useState('auto');
 const [result,setResult]=useState<ReplyResult|null>(null),[draft,setDraft]=useState(''),[error,setError]=useState(''),[phase,setPhase]=useState('');
 const [dragging,setDragging]=useState(false),[preview,setPreview]=useState<ReplyImage|null>(null),[linked,setLinked]=useState(''),[saved,setSaved]=useState(false);
 const fileInput=useRef<HTMLInputElement>(null),outputHeading=useRef<HTMLHeadingElement>(null),alive=useRef(true),working=useRef(false);
 const allowed=source.can('AIReplyDraft','create'),busy=!!phase;
 const direction=analysis?.directions.find(d=>d.id===selected);
 const ready=allowed&&!busy&&canGenerate(text,direction,custom);
 const changedTranslation=!!result&&draft!==result.draftText;
 useEffect(()=>{alive.current=true;return()=>{alive.current=false}},[]);
 useEffect(()=>{if(analysis||result)outputHeading.current?.focus()},[analysis,result]);
 useEffect(()=>{
  if(!route.id)return;
  let current=true;working.current=true;setPhase('正在读取会话');
  Promise.all([source.get(`ExternalConversation/${route.id}`),source.list('ExternalMessage',{where:[{type:'equals',attribute:'conversationId',value:route.id}],orderBy:'sentAt',order:'desc',limit:20})])
   .then(([conversation,messages])=>{if(!current)return;setLinked(conversation.accountName||conversation.name||'当前会话');setText([...messages.list].reverse().map(m=>`${m.direction==='inbound'?'客户':'业务员'}：${m.body||''}`).join('\n\n').slice(-12000));})
   .catch(()=>{if(current)setError('无法读取关联会话，请返回消息中心重试；也可以在这里上传截图。')})
   .finally(()=>{if(current){working.current=false;setPhase('')}});
  return()=>{current=false};
 },[route.id,source]);
 const clearResult=()=>{setResult(null);setDraft('');setSaved(false);setError('')};
 const changeText=(value:string)=>{setText(value);setAnalysis(null);setSelected('');clearResult()};
 const invalidateImages=()=>{setText('');setAnalysis(null);setSelected('');clearResult()};
 async function addImages(files:File[]){
  if(working.current||!allowed)return;
  if(source.demo){setError('示例预览不识别上传截图。请切换真实数据使用，或点击“载入示例询盘”。');return}
  if(!files.length)return;
  const problem=validateFiles(images,files);if(problem){setError(problem);return}
  working.current=true;setPhase('正在读取截图');setError('');
  try{const added=await Promise.all(files.map(readImage));if(alive.current){setImages(previous=>[...previous,...added]);invalidateImages()}}
  catch(e){if(alive.current)setError(e instanceof Error?e.message:'读取失败，请重新选择截图。')}
  finally{working.current=false;if(alive.current)setPhase('')}
 }
 async function request(payload:Record<string,unknown>){
  const response=await source.post('Fusanhe/reply-assistant',payload);
  if(response?.ok!==true||!response.result)throw new Error('Invalid response');
  return response.result;
 }
 async function analyze(){
  if(working.current||!allowed||(!images.length&&!text.trim()))return;
  working.current=true;setPhase('正在识别客户诉求');setError('');
  try{
   if(source.demo){setAnalysis(sampleAnalysis);setText(sampleAnalysis.recognizedText);setSelected('');clearResult();return}
   const next:Analysis=await request({operation:'analyze',images:images.map(i=>i.dataUrl),text});
   if(!alive.current)return;
   setText(next.recognizedText);setAnalysis(next);setSelected('');clearResult();
  }catch(e){if(alive.current)setError(replyError(e))}
  finally{working.current=false;if(alive.current)setPhase('')}
 }
 async function generate(refinement:Refinement=''){
  if(working.current||!ready)return;
  working.current=true;setPhase(refinement?'正在调整回复':'正在生成回复');setError('');
  try{
   const next:ReplyResult=source.demo?sampleReply:await request(generationPayload(text,direction,custom,language,refinement?draft:'',refinement));
   if(!alive.current)return;
   setResult(next);setDraft(next.draftText);setSaved(false);
  }catch(e){if(alive.current)setError(replyError(e))}
  finally{working.current=false;if(alive.current)setPhase('')}
 }
 async function copy(){
  try{await navigator.clipboard.writeText(draft);notify('回复正文已复制')}
  catch{setError('浏览器未允许复制，请在回复框中全选并复制正文。')}
 }
 async function save(){
  if(working.current||!linked||!draft.trim()||saved||!allowed)return;
  working.current=true;setPhase('正在保存草稿');setError('');
  try{await source.post(`Fusanhe/conversation/${route.id}/manual-draft`,{draftText:draft});if(alive.current){setSaved(true);notify(source.demo?'示例草稿已保存，未发送':'草稿已保存到原会话，未发送')}}
  catch{if(alive.current)setError('未确认草稿是否保存成功，请先到原会话核对，避免重复保存。')}
  finally{working.current=false;if(alive.current)setPhase('')}
 }
 return <div className="ra-page" onPaste={e=>{const files=Array.from(e.clipboardData.files);if(files.length){e.preventDefault();void addImages(files)}}}>
  <ol className="ra-steps" aria-label="回复步骤"><li className={!analysis&&!result?'current':''}><span>1</span>提供聊天内容</li><li className={analysis&&!result?'current':''}><span>2</span>确定回复思路</li><li className={result?'current':''}><span>3</span>编辑并复制回复</li></ol>
  {source.demo&&<Notice>当前为合成示例，展示固定回复，不识别截图或执行自定义要求。<Button onClick={()=>{setText(sampleAnalysis.recognizedText);setAnalysis(sampleAnalysis);setSelected('');clearResult()}}>载入示例询盘</Button></Notice>}
  {!allowed&&<Notice>当前账号没有 AI 草稿创建权限，请联系管理员开通后使用。</Notice>}
  {linked&&<div className="ra-linked"><FileText size={16}/><span>已带入 {linked} 的最近 20 条已同步消息</span><button type="button" className="w-link" onClick={()=>navigate('messages',{id:route.id})}>返回会话</button></div>}
  {error&&<div className="ra-error" role="alert">{error}<button type="button" aria-label="关闭错误提示" onClick={()=>setError('')}><X size={16}/></button></div>}
  <div className="ra-layout" aria-busy={busy}>
   <section className="w-panel ra-source" aria-labelledby="ra-source-title">
    <header className="ra-heading"><div><h2 id="ra-source-title">客户说了什么？</h2><p>上传聊天截图，也可以直接粘贴文字。</p></div><ImagePlus size={21}/></header>
    <fieldset disabled={busy||!allowed}>
     <div className={'ra-upload'+(dragging?' dragging':'')} onDragOver={e=>{e.preventDefault();if(!busy)setDragging(true)}} onDragLeave={()=>setDragging(false)} onDrop={e=>{e.preventDefault();setDragging(false);void addImages(Array.from(e.dataTransfer.files))}}>
      <input ref={fileInput} type="file" accept="image/png,image/jpeg,image/webp" multiple className="w-sr" aria-label="上传聊天截图" onChange={e=>{void addImages(Array.from(e.target.files||[]));e.target.value=''}}/>
      <Upload size={25} strokeWidth={1.6}/><strong>拖入截图，或粘贴到这里</strong>
      <Button onClick={()=>fileInput.current?.click()}>选择截图</Button><small>PNG / JPG / WebP · 最多 3 张 · 每张 4 MB</small>
     </div>
     {!!images.length&&<ol className="ra-images">{images.map((img,i)=><li key={img.id}><button type="button" className="ra-thumb" onClick={()=>setPreview(img)} aria-label={`查看截图 ${i+1}`}><img src={img.dataUrl} alt={`聊天截图 ${i+1}`}/></button><div><strong>截图 {i+1}</strong><small>{img.name}</small></div><button type="button" className="ra-remove" aria-label={`移除截图 ${i+1}`} onClick={()=>{setImages(images.filter(x=>x.id!==img.id));invalidateImages()}}><X size={16}/></button></li>)}</ol>}
     <label className="ra-field" htmlFor="ra-text"><span>{analysis?'识别内容 · 可以修正':'聊天文字'}<small>{text.length}/12000</small></span><textarea id="ra-text" value={text} maxLength={12000} rows={7} placeholder={'例如：\n客户：你们的报价比其他供应商高，能优惠一些吗？'} onChange={e=>changeText(e.target.value)}/></label>
     {analysis?.summaryZh&&<div className="ra-summary"><h3>客户诉求</h3><p>{analysis.summaryZh}</p></div>}
     {!!analysis?.warnings.length&&<div className="ra-warning"><h3>需要补充</h3><ul>{analysis.warnings.map((w,i)=><li key={i}>{w}</li>)}</ul></div>}
     <Button primary disabled={busy||!allowed||(!images.length&&!text.trim())} onClick={()=>void analyze()}>{phase==='正在识别客户诉求'?<RefreshCw size={16} className="w-spin"/>:<MessageSquareReply size={16}/>} {analysis?'重新分析回复方向':'分析回复方向'}</Button>
     <p className="ra-help">点击分析后，截图会交由 AI 识别。请检查识别内容，再确定回复思路。</p>
    </fieldset>
   </section>
   <section className="w-panel ra-output" aria-labelledby="ra-output-title">
    <header className="ra-heading"><div><h2 ref={outputHeading} tabIndex={-1} id="ra-output-title">{result?'回复已起草，检查后再使用':'你想怎么回复？'}</h2><p>{result?'正文可以直接修改，复制时只包含回复内容。':'选一个方向，再补充要求；也可以直接写下你的想法。'}</p></div>{result?<Check size={21}/>:<MessageSquareReply size={21}/>}</header>
    <fieldset disabled={busy||!allowed}>
     {result?<>
      <div className="ra-current"><div><small>本次回复思路</small><strong>{direction?.title||'按自定义思路回复'}</strong>{custom&&<p>{custom}</p>}</div><Button onClick={clearResult}><ArrowLeft size={15}/>修改方向</Button></div>
      {result.conflictNote&&<Notice>{result.conflictNote}</Notice>}
      <label className="ra-field" htmlFor="ra-draft"><span>回复正文<small>可编辑</small></span><textarea id="ra-draft" dir="auto" value={draft} maxLength={12000} rows={9} onChange={e=>{setDraft(e.target.value);setSaved(false)}}/></label>
      <div className="ra-refine" aria-label="调整回复"><span>调整表达</span>{([{id:'shorter',name:'简短一点'},{id:'natural',name:'更自然'},{id:'formal',name:'更正式'}] as const).map(item=><button type="button" key={item.id} disabled={!draft.trim()} onClick={()=>void generate(item.id)}>{item.name}</button>)}</div>
      <details className="ra-translation" open={!changedTranslation}><summary>中文释义{changedTranslation?' · 正文已修改，以下为修改前的释义':''}</summary><p>{result.translationZh}</p></details>
      {!!result.missingInformation.length&&<div className="ra-warning"><h3>发送前待确认</h3><ul>{result.missingInformation.map((v,i)=><li key={i}>{v}</li>)}</ul></div>}
      <div className="ra-actions"><Button primary disabled={!draft.trim()} onClick={()=>void copy()}><Copy size={16}/>复制回复</Button>{linked&&<Button disabled={!draft.trim()||saved} onClick={()=>void save()}>{saved?<Check size={16}/>:<FileText size={16}/>} {saved?'已保存草稿':'保存到会话草稿'}</Button>}</div>
      <p className="ra-help">回复尚未发送。请核对价格、交期与产品信息后使用。</p>
     </>:<>
      {analysis?.directions.length?<div className="ra-directions" role="group" aria-label="选择回复方向">{analysis.directions.map((d,i)=><button type="button" key={d.id} className={'ra-direction'+(selected===d.id?' selected':'')} aria-pressed={selected===d.id} onClick={()=>{setSelected(selected===d.id?'':d.id);clearResult()}}><span className="ra-choice">{selected===d.id?<Check size={16}/>:i+1}</span><span><strong>{d.title}</strong><small>{d.description}</small></span></button>)}</div>:<div className="ra-direction-empty"><MessageSquareReply size={28} strokeWidth={1.4}/><h3>先了解客户，再决定怎么回</h3><p>分析聊天内容后，这里会出现 3 个回复方向。<br/>已有明确想法？填写聊天文字后，可直接自定义。</p></div>}
      <label className="ra-field" htmlFor="ra-custom"><span>你想怎么回？<small>{custom.length}/1500</small></span><textarea id="ra-custom" value={custom} maxLength={1500} rows={4} onChange={e=>{setCustom(e.target.value);clearResult()}} placeholder="例如：先别降价，问他预计采购量，语气客气一点。"/></label>
      <p className="ra-help">可补充所选方向，也可单独填写。与方向冲突时，以你的要求为准。</p>
      <label className="ra-language" htmlFor="ra-language"><span>回复语言</span><select id="ra-language" value={language} onChange={e=>{setLanguage(e.target.value);clearResult()}}>{languages.map(l=><option key={l.id} value={l.id}>{l.name}</option>)}</select></label>
      <div className="ra-actions"><Button primary disabled={!ready} onClick={()=>void generate()}>按这个思路生成回复<ArrowRight size={16}/></Button></div>
     </>}
    </fieldset>
   </section>
  </div>
  <div className="ra-progress" role="status" aria-live="polite">{busy&&<><RefreshCw size={16} className="w-spin"/>{phase}…</>}</div>
  {preview&&<Dialog title="聊天截图预览" onClose={()=>setPreview(null)}><div className="w-dialog-body ra-preview"><img src={preview.dataUrl} alt="聊天截图原图"/></div></Dialog>}
 </div>;
}
