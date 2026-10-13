import {useEffect,useRef,useState} from 'react';
import {ChevronDown,ChevronUp,RefreshCw,ExternalLink,CheckCircle,AlertCircle} from 'lucide-react';
import type {DataSource} from './bridge';
import type {Row} from './domain';
import {date} from './domain';
import {Button,Drawer,Facts,Notice,Empty} from './ui';
import {assessCapture,platforms,type Capture} from './capture-model';
import type {Navigate} from './main';
import {CardStatus} from './card-status';
export function CaptureStrip({source,compact=false,navigate}:{source:DataSource;compact?:boolean;navigate?:Navigate}){
 const [states,setStates]=useState<Capture[]>(platforms.map(p=>assessCapture(p.type,[],[]))),[busy,setBusy]=useState(false),[error,setError]=useState(''),[selected,setSelected]=useState(''),[collapsed,setCollapsed]=useState<Record<string,string>>({}),[recovered,setRecovered]=useState<Record<string,number>>({});
 const [history,setHistory]=useState<{type:string;at:string;state:string;reason:string}[]>([]);
 const [revision,setRevision]=useState(0);
 const inFlight=useRef(false),mounted=useRef(true),previous=useRef<Capture[]>([]);
 const check=async()=>{if(inFlight.current)return;inFlight.current=true;setBusy(true);setError('');setRevision(v=>v+1);try{
 const channels=await source.list('ExternalChannel',{limit:100});
 const agents=source.can('AutomationAgent','read')?await source.list('AutomationAgent',{limit:100}):{list:[]};
 const observations:Row[]=[];
 for(const channel of channels.list){if(!platforms.some(p=>p.type===channel.type))continue;const latest=await source.list('ExternalConversation',{where:[{type:'equals',attribute:'channelId',value:channel.id},{type:'isNotNull',attribute:'lastSourceSyncAt'}],orderBy:'lastSourceSyncAt',limit:1});observations.push({...channel,lastSyncAt:channel.lastSyncAt||latest.list[0]?.lastSourceSyncAt});}
 const next=platforms.map(p=>assessCapture(p.type,observations,agents.list));
 if(!mounted.current)return;
 const before=previous.current;
 setHistory(old=>[...next.filter(s=>{const prev=before.find(p=>p.type===s.type);return s.state!=='checking'&&(prev?.state!==s.state||prev?.reason!==s.reason)}).map(s=>({type:s.type,at:new Date().toISOString(),state:s.state,reason:s.reason})),...old].slice(0,30));
 setRecovered(old=>{const n={...old};next.forEach(s=>{if(s.state==='healthy'&&before.find(p=>p.type===s.type)?.state==='error')n[s.type]=Date.now()});return n});setCollapsed(old=>{const n={...old};next.forEach(s=>{if(before.find(p=>p.type===s.type)?.state!=='error')delete n[s.type]});return n});previous.current=next;setStates(next);
 }catch{if(mounted.current)setError('状态检查失败，请重试。原有异常状态已保留。')}finally{inFlight.current=false;if(mounted.current)setBusy(false)}};
 useEffect(()=>{mounted.current=true;void check();const timer=setInterval(()=>void check(),30000);return()=>{mounted.current=false;clearInterval(timer)}},[source]);
 const chosen=states.find(s=>s.type===selected);
 const action=(s:Capture)=>s.agents.some(a=>a.status==='loginExpired'||['login_required','authentication_required'].includes(a.lastError))?'处理登录':s.agents.some(a=>a.status==='captcha'||a.lastError==='verification_required')?'处理验证码':'查看详情';
 return <><section className={'w-capture-strip'+(compact?' compact':'')} aria-label="平台抓取状态">{states.map(s=>{
 const expanded=s.state==='error'&&collapsed[s.type]!==s.reason;
 const recovering=s.state==='healthy'&&Date.now()-(recovered[s.type]||0)<60000;
 return <div key={s.type} className={'w-capture '+s.state+(expanded?' expanded':'')}>
 <button className="w-capture-summary" onClick={()=>setSelected(s.type)}><span className="w-health-dot"/><strong>{s.name}</strong><span>{s.state==='error'?'抓取异常':s.state==='healthy'?recovering?'已恢复正常':'抓取正常':busy?'正在检查':'待核查'}</span><small>最近抓取 {s.lastSuccessAt?date(s.lastSuccessAt,true):'暂无记录'}</small></button>
 {s.state==='error'&&<button className="w-icon" aria-label={expanded?'收起异常详情':'展开异常详情'} onClick={()=>setCollapsed({...collapsed,[s.type]:expanded?s.reason:''})}>{expanded?<ChevronUp size={15}/>:<ChevronDown size={15}/>}</button>}
 {expanded&&<div className="w-capture-error"><p>{s.reason}</p><small>最近成功抓取：{s.lastSuccessAt?date(s.lastSuccessAt,true):'暂无记录'} · 异常发现：{date(history.find(h=>h.type===s.type&&h.state==='error')?.at,true)}</small><div className="w-capture-actions"><Button onClick={()=>setSelected(s.type)}>{action(s)}</Button><Button disabled={busy} onClick={()=>void check()}><RefreshCw size={14}/>{busy?'检查中…':'重新检查'}</Button><button className="w-link" onClick={()=>setSelected(s.type)}>查看详情</button></div></div>}
 </div>})}<CardStatus source={source} revision={revision} openAcquisition={navigate?()=>navigate('acquisition'):undefined}/><button className="w-icon w-capture-refresh" aria-label="重新检查平台状态" disabled={busy} onClick={()=>void check()}><RefreshCw size={15} className={busy?'w-spin':''}/></button></section>{error&&<p className="w-inline-error" role="alert">{error}</p>}
 {chosen&&<Drawer title={chosen.name+' · 抓取状态'} onClose={()=>setSelected('')}><Notice>{chosen.state==='healthy'?'抓取正常；没有新消息也属于正常抓取。':chosen.reason}</Notice><Facts items={[["最近成功抓取",date(chosen.lastSuccessAt||undefined,true)],["最近检查",date(chosen.lastCheckAt||undefined,true)],["平台账号",chosen.channels.map(c=>c.name).join('、')],["执行端",chosen.agents.map(a=>a.name).join('、')]]}/><p className="w-muted">时间来自抓取系统已报告的成功同步记录。授权连接正常与抓取成功分别核对。</p><Button disabled={busy} onClick={()=>void check()}>{busy?'检查中…':'重新检查'}</Button><h3>状态变化记录</h3>{history.filter(h=>h.type===chosen.type).map((h,i)=><p key={i} className="w-muted">{date(h.at,true)} · {h.state==='healthy'?'正常 / 已恢复':h.reason}</p>)}<small className="w-muted">本次工作台会话观察到的变化；不代表全部采集历史。</small><h3>账号处理</h3><p>在已登录的平台采集主机处理登录或验证码，然后重新检查状态。</p><a className="w-link" href={chosen.type==='Alibaba'?'https://message.alibaba.com/':'https://www.made-in-china.com/'} target="_blank" rel="noreferrer">打开平台<ExternalLink size={14}/></a><h3>执行端记录</h3>{chosen.agents.length?chosen.agents.map(a=><div className="w-operation-row" key={a.id}><strong>{a.name}</strong><span>{a.status==='online'?'在线':a.status}</span><small>{date(a.lastHeartbeatAt,true)}</small></div>):<Empty title="暂无执行端记录" detail="采集系统报告状态后会显示在这里。"/>}</Drawer>}
 </>
}
