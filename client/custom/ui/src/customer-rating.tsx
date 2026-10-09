import {type Row,date} from './domain';
import {Facts,Rating,Notice} from './ui';
import type {Navigate} from './main';
export const ratingLabels:Record<string,string>={S:'超高',A:'高',B:'中',C:'低',D:'超低'};
export const ratingStates:Record<string,string>={pending:'等待自动评级',running:'正在检索与评级',failed:'评级失败，稍后重试',completed:'已完成'};
function webUrl(value:unknown):string|undefined{try{const u=new URL(String(value));return ['https:','http:'].includes(u.protocol)?u.href:undefined}catch{return undefined}}
export function CustomerRatingEvidence({row,navigate,sectioned=true}:{row:Row;navigate:Navigate;sectioned?:boolean}){
 const d=row.aiRatingData||{};const company=d.company||{};const sources=Array.isArray(d.sources)?d.sources:[];
 return <div className={'w-rating-evidence'+(sectioned?' w-inspector-section':'')}><p><Rating value={row.rating}/> <span className="w-muted">{row.ratingSource==='manual'?'人工调整':row.ratingSource==='auto'?'AI 自动评级':row.rating?'人工评级':ratingStates[row.aiRatingStatus]||'等待自动评级'}</span></p>
 {row.aiRatingStatus==='failed'&&<Notice>本次检索或模型调用未完成，已有评级保留。系统最多自动重试 3 次。</Notice>}
 {row.aiRatingReason&&<><h3>评级依据</h3><p>{row.aiRatingReason}</p>{row.ratingSource==='manual'&&<p>AI 当前建议：<Rating value={row.aiRating}/></p>}</>}
 <Facts items={[["评级时间",date(row.aiRatingAt,true)],["分析模型",row.aiRatingModel],["证据充分程度",({high:'较充分',medium:'一般',low:'有限'} as Record<string,string>)[d.confidence]],["公司核实",({confirmed:'已匹配',possible:'候选，待核实',unverified:'未核实'} as Record<string,string>)[company.matchStatus]]]}/>
 {company.name&&<p><strong>{company.name}</strong>{webUrl(company.website)&&<> · <a href={webUrl(company.website)} target="_blank" rel="noreferrer">查看公司网站</a></>}</p>}
 {company.reason&&<p>{company.reason}</p>}
 {d.nextAction&&<><h3>建议跟进</h3><p>{d.nextAction}</p></>}
 {Array.isArray(d.missingInformation)&&d.missingInformation.length>0&&<p className="w-muted">待补充：{d.missingInformation.join('；')}</p>}
 {sources.length>0&&<><h3>公开资料来源</h3><ul>{sources.map((s:Row,i:number)=>webUrl(s.url)?<li key={i}><a href={webUrl(s.url)} target="_blank" rel="noreferrer">{s.title||s.url}</a></li>:null)}</ul></>}
 {row.aiRatingStatus==='completed'&&!sources.length&&<p className="w-muted">已联网检索，尚无可靠公司来源；当前评级主要依据历史资料。</p>}
 {Array.isArray(d.evidence)&&d.evidence.length>0&&<details><summary>查看历史消息依据（{d.evidence.length}）</summary>{d.evidence.map((m:Row)=><p key={m.id}><button className="w-link" onClick={()=>navigate('messages',{id:m.conversationId,entity:m.id})}>{m.quote}</button></p>)}</details>}
 {d.historyTruncated&&<p className="w-muted">本次使用最近 {d.includedMessages} 条历史消息，完整记录共 {d.totalMessages} 条。</p>}
 </div>
}
