import {useEffect,useRef,useState} from 'react';
import {MessageCircle,Plus,RefreshCw,Check,Send,Link2,Unplug,ChevronRight,Trash2} from 'lucide-react';
import QRCode from 'qrcode';
import type {DataSource} from './bridge';
import {Avatar,Badge,Button,Field,Notice} from './ui';
import {date} from './domain';
import {accountState,canPoll,qrRemaining,wechatError,type WeChatAccount} from './wechat-model';
import {MorningReports} from './morning-report';

export function WeChatPage({source}:{source:DataSource}){
 const reportDate=new URLSearchParams(location.search).get('reportDate')||'';
 return reportDate?<MorningReports source={source} reportDate={reportDate}/>:<WeChatAccountsPage source={source}/>;
}
function WeChatAccountsPage({source}:{source:DataSource}){
 const [accounts,setAccounts]=useState<WeChatAccount[]>([]),[selectedId,setSelectedId]=useState(''),[loading,setLoading]=useState(true),[error,setError]=useState(''),[busy,setBusy]=useState(''),[adding,setAdding]=useState(false),[newName,setNewName]=useState(''),[editName,setEditName]=useState(''),[code,setCode]=useState(''),[image,setImage]=useState(''),[now,setNow]=useState(Date.now()),[pollError,setPollError]=useState(''),[success,setSuccess]=useState(''),[disconnecting,setDisconnecting]=useState(false);
 const latest=useRef({id:'',version:''});
 const pollGeneration=useRef(0);
 const [removing,setRemoving]=useState(false);
 const [agent,setAgent]=useState<{enabled:boolean;scope:string}|null>(null);
 const selected=accounts.find(a=>a.id===selectedId),qr=selected?.qr||null;
 latest.current={id:selectedId,version:qr?.version||''};
 const merge=(a:WeChatAccount)=>setAccounts(list=>list.some(x=>x.id===a.id)?list.map(x=>x.id===a.id?a:x):[...list,a]);
 const failure=(e:any)=>e?.status===403?'微信接入管理需要管理员权限。':wechatError(e?.responseJSON?.message||e?.message);
 const load=async()=>{setError('');setLoading(true);try{const result=source.demo?{accounts:[]}:await source.get('Fusanhe/wechat/accounts');setAccounts(result.accounts);setAgent(result.agent||null);setSelectedId(id=>result.accounts.some((a:WeChatAccount)=>a.id===id)?id:result.accounts[0]?.id||'')}catch(e){setError(failure(e))}finally{setLoading(false)}};
 useEffect(()=>{void load()},[source]);
 useEffect(()=>{setEditName(selected?.name||'')},[selectedId,selected?.name]);
 useEffect(()=>{setCode('');setDisconnecting(false);setRemoving(false);setSuccess('');setPollError('')},[selectedId]);
 useEffect(()=>{const timer=setInterval(()=>setNow(Date.now()),1000);return()=>clearInterval(timer)},[]);
 useEffect(()=>{let alive=true;setImage('');if(qr?.url)void QRCode.toDataURL(qr.url,{width:280,margin:4,errorCorrectionLevel:'M'}).then(url=>{if(alive)setImage(url)}).catch(()=>{if(alive)setError('二维码显示失败，请刷新重试。')});return()=>{alive=false}},[qr?.url,qr?.version]);
 useEffect(()=>{
  if(source.demo||!selected||!canPoll(qr))return;
  let alive=true,timer:ReturnType<typeof setTimeout>;const id=selected.id,version=qr!.version;
  const poll=async()=>{if(!canPoll(qr))return;const generation=pollGeneration.current;try{const r=await source.post('Fusanhe/wechat/accounts/'+id,{action:'poll',version});if(alive&&generation===pollGeneration.current&&latest.current.id===id&&latest.current.version===version){merge(r.account);setPollError('')}}catch(e){if(alive&&generation===pollGeneration.current)setPollError(failure(e))}finally{if(alive)timer=setTimeout(poll,3500)}};
  timer=setTimeout(poll,1000);return()=>{alive=false;clearTimeout(timer)};
 },[source,selectedId,qr?.version,qr?.state]);
 const perform=async(id:string,action:string,extra:Record<string,unknown>={})=>{
  setBusy(id+':'+action);setError('');setSuccess('');setPollError('');
  if(action==='refreshQr'){pollGeneration.current++;latest.current={id,version:'refreshing'}};
  try{const r=await source.post('Fusanhe/wechat/accounts/'+id,{action,...extra});if(action==='remove'){setAccounts(list=>list.filter(a=>a.id!==id));setSelectedId('');setRemoving(false);void load()}else merge(r.account);if(action==='test'&&r.account.testStatus==='sent')setSuccess('测试通知已发出，请到对应微信确认。');if(action==='rename')setSuccess('账号名称已保存。');if(action==='disconnect')setDisconnecting(false);return r.account as WeChatAccount}
  catch(e){setError(failure(e));return undefined}finally{setBusy('')}
 };
 const add=async()=>{if(!newName.trim()||busy)return;setBusy('create');setError('');try{const r=await source.post('Fusanhe/wechat/accounts',{name:newName.trim()});merge(r.account);setSelectedId(r.account.id);setAdding(false);setNewName('');await perform(r.account.id,'refreshQr')}catch(e){setError(failure(e))}finally{setBusy('')}};
 const configureAgent=async(enabled:boolean)=>{setBusy('agent');setError('');try{const r=await source.post('Fusanhe/wechat/agent',{enabled});setAgent(r.agent)}catch(e){setError(failure(e))}finally{setBusy('')}};
 const seconds=qrRemaining(qr,now),expired=qr?.state==='expired'||(!!qr&&seconds===0);
 const qrState=expired?'二维码已过期':qr?.state==='scaned'?'已扫码，请在手机确认':qr?.state==='need_verifycode'?'输入微信显示的配对码':qr?.state==='error'?'二维码暂不可用':'等待微信扫码';
 const bound=selected?.status==='bound',pendingQr=!!qr;
 return <section aria-label="微信接入账号管理" className="w-wechat">
  <MorningReports source={source} recipients={accounts.filter(a=>a.status==='bound'&&a.enabled).length}/>
  {agent&&<section className="w-morning" aria-label="微信客户助手"><div className="w-morning-toolbar"><div className="w-morning-title"><MessageCircle size={17}/><div><strong>微信客户助手</strong><span>查看全部 CRM 客户 · 调出沟通记录 · 确认后录入客户</span></div><Badge tone={agent.enabled?'success':'neutral'}>{agent.enabled?'已开启':'已暂停'}</Badge></div><label className="w-agent-toggle"><input type="checkbox" role="switch" aria-label="开启微信客户助手" checked={agent.enabled} disabled={!!busy||loading} onChange={e=>configureAgent(e.target.checked)}/>开启客户助手</label></div><p className="w-agent-examples">在微信说“列出客户”“找德国的 A 级客户”“查看第 2 个”，或直接发送客户资料。每次最多添加 10 位客户，先预览，再回复确认码录入。</p><p className="w-muted">所有开启客户助手的绑定账号，都可以查询和录入全部客户；新增记录默认是潜在客户，保留发起微信账号的操作记录。</p></section>}
  <div className="w-wechat-toolbar"><div><strong>接收账号</strong><span className="w-muted">{accounts.length} 个账号 · {accounts.filter(a=>a.status==='bound').length} 个已绑定</span></div><div><Button disabled={loading||!!busy} onClick={load}><RefreshCw size={14}/>刷新列表</Button><Button primary disabled={source.demo||!!busy} onClick={()=>{setAdding(true);setError('')}}><Plus size={15}/>添加账号</Button></div></div>
  {source.demo&&<Notice>微信接入使用真实扫码授权。请切换到真实数据后管理接收账号。</Notice>}
  {error&&<p className="w-wechat-error" role="alert">{error}</p>}
  <div className="w-wechat-layout">
   <aside className="w-wechat-list" aria-label="微信接收账号"><div className="w-wechat-list-head"><span>账号名称</span><span>连接状态</span></div>
    {loading&&!accounts.length?<p className="w-wechat-placeholder" role="status">正在读取账号…</p>:!accounts.length?<div className="w-wechat-placeholder"><MessageCircle size={22}/><strong>暂无接收账号</strong><p>添加接收人，再用对应微信扫码绑定。</p></div>:accounts.map(a=><button type="button" key={a.id} aria-pressed={a.id===selectedId} className={'w-wechat-row'+(a.id===selectedId?' selected':'')} onClick={()=>{setSelectedId(a.id);setAdding(false);setError('')}}><Avatar name={a.name}/><span><strong>{a.name}</strong><small>{a.boundAt?'绑定于 '+date(a.boundAt):'等待扫码绑定'}</small></span><Badge tone={a.status==='bound'&&a.enabled?'success':'neutral'}>{accountState(a)}</Badge><ChevronRight size={14}/></button>)}
    <p className="w-wechat-list-note">每个接收人使用自己的微信绑定，通知分别发送到私聊。</p>
   </aside>
   <div className="w-wechat-detail">
    {adding?<form className="w-wechat-add" onSubmit={e=>{e.preventDefault();void add()}}><h2>添加微信接收账号</h2><p>先为接收人命名，例如“负责人”或“销售主管”，再扫码绑定。</p><Field label="接收人名称"><input autoFocus maxLength={60} required value={newName} placeholder="输入便于识别的名称" onChange={e=>setNewName(e.target.value)}/></Field><div className="w-form-actions"><Button primary type="submit" disabled={!newName.trim()||!!busy}>{busy?'正在准备…':'添加并生成二维码'}</Button><Button disabled={!!busy} onClick={()=>setAdding(false)}>取消</Button></div></form>:!selected?<div className="w-wechat-intro"><Link2 size={26}/><h2>把 CRM 提醒送到微信</h2><p>添加接收账号，用该接收人的微信扫码确认。每个账号都有独立的二维码，可以随时刷新。</p><ol><li>添加接收人名称</li><li>使用对应微信扫码授权</li><li>发送一条测试通知</li></ol><Button primary disabled={source.demo||!!busy} onClick={()=>setAdding(true)}><Plus size={15}/>添加第一个账号</Button><p className="w-muted">启用提醒的已绑定账号，将收到同一份每日晨报。</p></div>:<>
     <header className="w-wechat-detail-head"><Avatar name={selected.name}/><div><h2>{selected.name}</h2><p>{bound?'微信已绑定，可检查提醒是否送达。':'请使用这个接收人的微信完成扫码。'}</p></div><Badge tone={bound&&selected.enabled?'success':'neutral'}>{accountState(selected)}</Badge></header>
     <div className="w-wechat-bind-area">
      {bound&&!pendingQr?<div className="w-wechat-bound"><span className="w-wechat-bound-icon"><Check size={28}/></span><h3>微信已绑定</h3><p>在微信 ClawBot 中发一条消息，再发送测试通知确认接收。</p><Button primary disabled={!!busy||!selected.enabled} onClick={()=>perform(selected.id,'test')}><Send size={15}/>{busy===selected.id+':test'?'正在发送…':'发送测试通知'}</Button><p className="w-muted">{selected.lastTestAt?'最近测试通知：'+date(selected.lastTestAt,true):'尚未发送测试通知'}</p></div>:<div className="w-wechat-qr-content"><div className={'w-wechat-qr-frame'+(expired?' expired':'')}>
       {image&&!expired&&!busy.endsWith(':refreshQr')?<img src={image} alt={selected.name+'的微信绑定二维码'} width={252} height={252}/>:<div className="w-wechat-qr-placeholder"><MessageCircle size={34}/><span>{busy.endsWith(':refreshQr')?'正在生成二维码…':expired?'二维码已过期':qr?.state==='error'?'请重新获取二维码':'准备微信绑定'}</span></div>}
      </div><div className="w-wechat-qr-copy"><h3>{pendingQr?qrState:'扫码绑定微信'}</h3><p>用 <strong>{selected.name}</strong> 的手机微信“扫一扫”，并在手机上确认连接。</p>{qr&&!expired&&qr.state!=='error'&&<p className="w-wechat-countdown" aria-live="off">剩余 {Math.floor(seconds/60)} 分 {String(seconds%60).padStart(2,'0')} 秒</p>}
       <Button primary disabled={!!busy} onClick={()=>perform(selected.id,'refreshQr')}><RefreshCw size={15}/>{pendingQr?'刷新二维码':'生成二维码'}</Button><p className="w-muted">刷新后，请使用这里的新二维码完成绑定。</p>
       {bound&&pendingQr&&<Button disabled={!!busy} onClick={()=>perform(selected.id,'cancelQr')}>取消重新绑定</Button>}
       {qr?.state==='need_verifycode'&&!expired&&<form onSubmit={e=>{e.preventDefault();void perform(selected.id,'verify',{version:qr.version,code})}}><Field label="微信配对码"><input inputMode="numeric" autoComplete="one-time-code" pattern="[0-9]{4,12}" maxLength={12} value={code} onChange={e=>setCode(e.target.value.replace(/\D/g,''))} placeholder="输入手机微信显示的数字"/></Field><Button type="submit" disabled={!!busy||code.length<4}>确认配对码</Button></form>}
       {pollError&&<p className="w-wechat-error" role="status">{pollError}</p>}
      </div></div>}
     </div>
     {selected.error&&<p className="w-wechat-error" role="alert">{wechatError(selected.error)}</p>}{success&&<p className="w-wechat-success" role="status"><Check size={15}/>{success}</p>}
     <section className="w-wechat-settings"><h3>账号设置</h3><form className="w-wechat-name-form" onSubmit={e=>{e.preventDefault();void perform(selected.id,'rename',{name:editName})}}><Field label="接收人名称"><input maxLength={60} required value={editName} onChange={e=>setEditName(e.target.value)}/></Field><Button type="submit" disabled={!!busy||!editName.trim()||editName.trim()===selected.name}>保存名称</Button></form>
      <label className="w-wechat-switch"><span><strong>允许接收 CRM 提醒</strong><small>开启后接收统一晨报；停用后，这个账号不再接收新的提醒。</small></span><input type="checkbox" role="switch" checked={selected.enabled} disabled={!!busy} onChange={e=>perform(selected.id,'enable',{enabled:e.target.checked})}/></label>
      <label className="w-wechat-switch"><span><strong>允许通过微信操作 CRM</strong><small>开启后可查询全部客户、查看沟通记录、确认录入客户。{selected.lastAgentAt?'最近回复：'+date(selected.lastAgentAt,true)+(selected.agentStatus==='sent'?' · 已发送':selected.agentStatus==='uncertain'?' · 结果待确认':' · 发送失败'):''}</small></span><input type="checkbox" role="switch" checked={selected.agentEnabled!==false} disabled={!!busy} onChange={e=>perform(selected.id,'agent',{enabled:e.target.checked})}/></label>
      {bound&&<div className="w-wechat-connection-actions"><Button disabled={!!busy} onClick={()=>perform(selected.id,'refreshQr')}><RefreshCw size={14}/>重新绑定微信</Button>{disconnecting?<div className="w-wechat-confirm" role="group" aria-label="确认断开连接"><span>断开后需要重新扫码，才能接收提醒。</span><Button disabled={!!busy} onClick={()=>perform(selected.id,'disconnect')}>确认断开</Button><Button onClick={()=>setDisconnecting(false)}>取消</Button></div>:<Button disabled={!!busy} onClick={()=>setDisconnecting(true)}><Unplug size={14}/>断开 CRM 连接</Button>}</div>}
      <div className="w-wechat-connection-actions">{removing?<div className="w-wechat-confirm" role="group" aria-label="确认移除账号"><span>移除“{selected.name}”后，它将不再接收提醒。</span><Button disabled={!!busy} onClick={()=>perform(selected.id,'remove')}>确认移除</Button><Button onClick={()=>setRemoving(false)}>取消</Button></div>:<Button disabled={!!busy} onClick={()=>setRemoving(true)}><Trash2 size={14}/>移除账号</Button>}</div>
     </section>
    </>}
   </div>
  </div>
 </section>;
}
