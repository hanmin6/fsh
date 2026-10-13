import {useEffect,useState} from 'react';
import type {DataSource} from './bridge';
import {Button,Field,Notice} from './ui';
type Settings={enabled:boolean;workdayStart:string;workdayEnd:string;restdayAllDay:boolean;dateOverrides:Record<string,'work'|'rest'>;revision:number};
const demoSettings:Settings={enabled:true,workdayStart:'19:00',workdayEnd:'09:00',restdayAllDay:true,dateOverrides:{},revision:0};
export function ReceptionSettings({source}:{source:DataSource}){
 const [data,setData]=useState<any>(),[form,setForm]=useState<Settings>(),[saving,setSaving]=useState(false),[error,setError]=useState(''),[success,setSuccess]=useState(''),[date,setDate]=useState(''),[kind,setKind]=useState<'work'|'rest'>('work');
 const load=async()=>{setError('');try{const result=source.demo?{settings:demoSettings,state:{active:true,dayKind:'rest',calendarCovered:true,calendarYears:[2026]},canEdit:true,executionReady:true}:await source.get('Fusanhe/reception/settings');setData(result);setForm(result.settings)}catch{setError('自动回复设置读取失败，请重试。')}};
 useEffect(()=>{let alive=true;void load();if(source.demo)return()=>{alive=false};const timer=setInterval(()=>{source.get('Fusanhe/reception/settings').then(r=>{if(alive)setData((previous:any)=>({...previous,state:r.state,executionReady:r.executionReady}))}).catch(()=>{})},30000);return()=>{alive=false;clearInterval(timer)}},[source]);
 const update=(patch:Partial<Settings>)=>{setForm(f=>f?{...f,...patch}:f);setSuccess('')};
 const save=async()=>{if(!form)return;setSaving(true);setError('');setSuccess('');try{const result=source.demo?{...data,settings:form}:await source.post('Fusanhe/reception/settings',form);setData(result);setForm(result.settings);setSuccess(source.demo?'示例设置已更新，未影响真实自动回复。':'设置已保存，新的接待时间已生效。')}catch(e:any){setError(e?.status===409?'设置已被其他人更新，请重新读取后修改。':e?.status===403?'只有管理员可以修改自动回复设置。':'保存失败，请检查时间和日期后重试。')}finally{setSaving(false)}};
 return <section aria-label="自动回复设置"><h3>AI 自动回复</h3><p className="w-muted">北京时间。非工作时间 AI 先接待所有价值等级，工作时间高价值客户（S/A）交回人工。人工主动接管优先。</p>
 {error&&<p role="alert" className="w-error">{error}</p>}{success&&<p role="status">{success}</p>}
 {!form?<Button onClick={load}>重新读取设置</Button>:<>
 <Notice>{data.state?.active?(data.executionReady?'当前为 AI 接待时段 · 执行端就绪':'当前为 AI 接待时段 · 执行端暂未就绪'):'当前为人工接待时段'} · 今天为{data.state?.dayKind==='work'?'工作日':'休息日'}。{!data.state?.calendarCovered?'当前年份的法定调休表尚未录入，自动接待暂停。':''}</Notice>
 <fieldset disabled={!data.canEdit||saving} style={{border:0,padding:0,margin:'16px 0'}}><label className="w-checkbox"><input type="checkbox" checked={form.enabled} onChange={e=>update({enabled:e.target.checked})}/>启用非工作时间自动回复</label>
 <div className="w-form-grid"><Field label="工作日开始时间"><input type="time" required value={form.workdayStart} onChange={e=>update({workdayStart:e.target.value})}/></Field><Field label="工作日结束时间"><input type="time" required value={form.workdayEnd} onChange={e=>update({workdayEnd:e.target.value})}/></Field></div>
 <p className="w-muted">{form.workdayStart>form.workdayEnd?'跨天时段：开始至次日结束；结束时间起交回人工。':'当天时段：开始至结束；结束时间起交回人工。'}</p>
 <label className="w-checkbox"><input type="checkbox" checked={form.restdayAllDay} onChange={e=>update({restdayAllDay:e.target.checked})}/>休息日全天回复（含法定节假日）</label>
 <p className="w-muted">已录入 {data.state?.calendarYears?.join('、')} 年官方节假日及调休。调休补班按工作日处理；关闭全天回复后，休息日沿用上面的时间段。</p>
 <details><summary>公司作息与临时调休</summary><p className="w-muted">指定日期会覆盖官方日历，可用于临时加班或放假。</p><div className="w-form-grid"><Field label="例外日期"><input type="date" value={date} onChange={e=>setDate(e.target.value)}/></Field><Field label="当天类型"><select value={kind} onChange={e=>setKind(e.target.value as 'work'|'rest')}><option value="work">工作日</option><option value="rest">休息日</option></select></Field></div><Button disabled={!date} onClick={()=>{update({dateOverrides:{...form.dateOverrides,[date]:kind}});setDate('')}}>添加日期</Button>
 {Object.entries(form.dateOverrides).map(([d,k])=><p key={d}>{d} · {k==='work'?'工作日':'休息日'} <Button onClick={()=>{const next={...form.dateOverrides};delete next[d];update({dateOverrides:next})}}>移除</Button></p>)}</details>
 <div className="w-form-actions"><Button primary disabled={!form.workdayStart||!form.workdayEnd||form.workdayStart===form.workdayEnd} onClick={save}>{saving?'正在保存…':'保存自动回复设置'}</Button><Button onClick={load}>重新读取</Button></div></fieldset>
 {!data.canEdit&&<p className="w-muted">当前账号可查看设置；修改需要管理员权限。</p>}
 <p className="w-muted">自动接待先收集需求，报价和交期由人工确认。阿里巴巴已接通发送端，登录就绪后执行；中国制造网还需恢复登录并接通发送端。启用后只处理新消息。</p>
 </>}
 </section>;
}
