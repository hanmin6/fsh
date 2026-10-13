import {useEffect,useState} from 'react';
import {Clock,RefreshCw,FileText} from 'lucide-react';
import type {DataSource} from './bridge';
import {Badge,Button} from './ui';
import {date} from './domain';

type Settings={enabled:boolean;timezone:string;sendTime:string;firstDate:string|null};
type Delivery={name:string;status:string;error?:string;at?:string};
type Report={date:string;text:string;generatedAt:string;cutoff:string;warnings:string[];metrics:Record<string,number>;priorities:{name:string;reason:string;action:string;owner:string;url:string}[];deliveries?:Record<string,Delivery>};
const deliveryLabel:Record<string,string>={sent:'已发送',pending:'待发送',preparing:'发送中',uncertain:'结果待确认',failed:'发送失败',skipped:'已跳过'};
const deliveryError:Record<string,string>={report_rejected:'微信未接受推送，请先向微信 ClawBot 发一条消息并检查连接。',report_uncertain:'请先检查微信接收情况，系统不会自动重复发送。',report_context_unavailable:'未能取得微信会话，请检查连接并向 ClawBot 发一条消息。',report_cancelled:'发送前账号连接或提醒开关发生了变化。',account_unavailable:'账号已移除或连接不可用。',account_unbound:'账号尚未绑定。',account_disabled:'账号提醒已停用。'};

export function MorningReports({source,reportDate='',recipients=0}:{source:DataSource;reportDate?:string;recipients?:number}){
 const [settings,setSettings]=useState<Settings|null>(null),[report,setReport]=useState<Report|null>(null),[dates,setDates]=useState<string[]>([]),[loading,setLoading]=useState(true),[busy,setBusy]=useState(''),[error,setError]=useState(''),[preview,setPreview]=useState(false),[expanded,setExpanded]=useState(!!reportDate);
 const load=async(selectedDate=reportDate)=>{if(source.demo){setLoading(false);return}setLoading(true);setError('');try{const r=await source.get('Fusanhe/wechat/morning-report',selectedDate?{date:selectedDate}:{});if(r.settings)setSettings(r.settings);if(r.dates)setDates(r.dates);setReport(r.report);setPreview(false)}catch(e:any){setError(e?.status===403?'没有查看或管理晨报的权限。':'晨报读取失败，请重试。')}finally{setLoading(false)}};
 useEffect(()=>{void load()},[source,reportDate]);
 const configure=async(enabled:boolean)=>{setBusy('configure');setError('');try{const r=await source.post('Fusanhe/wechat/morning-report',{action:'configure',enabled});setSettings(r.settings)}catch{setError('晨报开关未保存，请重试。')}finally{setBusy('')}};
 const generate=async()=>{setBusy('preview');setError('');try{const r=await source.post('Fusanhe/wechat/morning-report',{action:'preview'});setReport(r.report);setPreview(true);setExpanded(true)}catch{setError('晨报生成失败，未发送任何消息。请检查 CRM 数据服务。')}finally{setBusy('')}};
 const standalone=!!reportDate;
 return <section className="w-morning" aria-label="每日微信晨报">
  <div className="w-morning-toolbar"><div className="w-morning-title"><Clock size={17}/><div><strong>{standalone?'完整晨报':'每日晨报'}</strong><span>{standalone?reportDate:'每天 09:00 · 北京时间 · 所有人收到相同内容'}</span></div>{settings&&<Badge tone={settings.enabled?'success':'neutral'}>{settings.enabled?'已开启':'已暂停'}</Badge>}</div><div className="w-morning-actions">{!standalone&&<Button disabled={source.demo||!!busy||loading} onClick={generate}><FileText size={14}/>{busy==='preview'?'正在生成…':'生成预览'}</Button>}<Button disabled={source.demo||!!busy||loading} onClick={()=>load()}><RefreshCw size={14}/>刷新</Button></div></div>
  {!standalone&&settings&&<div className="w-morning-settings"><label><input type="checkbox" role="switch" checked={settings.enabled} disabled={!!busy} onChange={e=>configure(e.target.checked)}/><span>每天自动发送晨报</span></label><p>{recipients} 个已绑定且启用提醒的账号{settings.enabled&&settings.firstDate?' · 已安排，自 '+settings.firstDate+' 起每日发送':''}。{!recipients?'绑定微信账号后即可接收。':''}</p></div>}
  {error&&<p className="w-wechat-error" role="alert">{error}</p>}
  {source.demo?<p className="w-muted">晨报根据真实 CRM 数据生成。请切换到真实数据查看。</p>:loading&&!report?<p className="w-muted" role="status">正在读取晨报…</p>:!report?<p className="w-muted">{standalone?'这一天的晨报尚未生成。':'尚无发送记录。可以先生成预览核对内容；预览不会发送到微信。'}</p>:<>
   <div className="w-morning-report-head"><strong>{report.date} {preview?'· 实时预览，未发送':'· 已保存晨报'}</strong><span className="w-muted">生成于 {date(report.generatedAt,true)}</span>{!standalone&&<Button onClick={()=>setExpanded(!expanded)}>{expanded?'收起内容':'查看内容与发送记录'}</Button>}</div>
   {expanded&&<div className="w-morning-content"><pre>{report.text}</pre><p className="w-muted">夜间统计：前一天 19:00 至当天 09:00；新增线索：前一天 00:00 至 24:00。联系方式按新建线索中的有效邮箱或电话计数，每条线索最多计一份；不计旧客户资料补全。{preview?' 此为预览，尚未保存或发送。':''}</p>
    {!!report.priorities.length&&<div className="w-morning-evidence"><strong>对应 CRM 记录</strong>{report.priorities.map((p,i)=><a key={i} href={p.url}>{['①','②','③'][i]} {p.name}<span>{p.reason} · {p.owner}</span></a>)}</div>}
    {!preview&&report.deliveries&&<div className="w-morning-deliveries"><strong>微信发送记录</strong>{!Object.keys(report.deliveries).length?<p className="w-muted">生成时没有已绑定且启用提醒的接收账号。</p>:Object.entries(report.deliveries).map(([id,d])=><div key={id}><span>{d.name}</span><Badge tone={d.status==='sent'?'success':d.status==='failed'||d.status==='uncertain'?'warning':'neutral'}>{deliveryLabel[d.status]||'待确认'}</Badge><small>{d.error?deliveryError[d.error]||'请检查账号连接。':d.at?date(d.at,true):''}</small></div>)}</div>}
   </div>}
  </>}
  {!standalone&&!!dates.length&&<label className="w-morning-history">历史晨报<select aria-label="选择历史晨报" value={!preview?report?.date||'':''} disabled={!!busy||loading} onChange={e=>{if(e.target.value){void load(e.target.value);setExpanded(true)}}}><option value="" disabled>选择日期</option>{dates.map(d=><option key={d} value={d}>{d}</option>)}</select></label>}
  {standalone&&<a className="w-morning-back" href="?workspace=wechat#Home/workspace">返回微信接入</a>}
 </section>;
}
