import {useEffect,useRef,useState} from 'react';
import {ChevronDown,ChevronUp,RefreshCw} from 'lucide-react';
import type {DataSource} from './bridge';
import {date} from './domain';
import {Button,Drawer,Facts,Notice} from './ui';

type Progress={date:string;statisticsDate:string;timezone:string;yesterdayAcquired:number;totalAcquired:number;yesterdayValueCounts:{high:number;medium:number;low:number;unrated:number};followUpCounts:{human:number;ai:number;pending_rating:number;blocked:number};lastAcquiredAt:string|null;checkedAt:string;outboundPaused:boolean};

export function CardStatus({source,revision,openAcquisition}:{source:DataSource;revision:number;openAcquisition?:()=>void}){
 const [savedProgress,setProgress]=useState<Progress|null>(null),[busy,setBusy]=useState(false),[error,setError]=useState(''),[expanded,setExpanded]=useState(true),[details,setDetails]=useState(false);
 const inFlight=useRef(false),sequence=useRef(0);
 const today=new Intl.DateTimeFormat('sv-SE',{timeZone:'Asia/Shanghai'}).format(new Date());
 const progress=savedProgress?.date===today?savedProgress:null;
 const check=async()=>{if(inFlight.current)return;inFlight.current=true;const request=++sequence.current;setBusy(true);try{const next=await source.get('Fusanhe/card-status');const counts=[next.yesterdayAcquired,next.totalAcquired,...Object.values(next.yesterdayValueCounts||{}),...Object.values(next.followUpCounts||{})];if(counts.length!==10||counts.some(n=>!Number.isInteger(n)||(n as number)<0)||!next.statisticsDate)throw Error('invalid status');if(sequence.current===request){setProgress(next);setError('')}}catch{if(sequence.current===request)setError('客资统计更新失败，请重新检查。')}finally{if(sequence.current===request){inFlight.current=false;setBusy(false)}}};
 useEffect(()=>{setProgress(null);setError('');inFlight.current=false;void check();return()=>{sequence.current++;inFlight.current=false}},[source]);
 useEffect(()=>{if(revision)void check()},[revision]);
 useEffect(()=>{const timer=setInterval(()=>void check(),60000);return()=>clearInterval(timer)},[source]);
 const count=progress?.yesterdayAcquired,values=progress?.yesterdayValueCounts,routes=progress?.followUpCounts;
 const state=error?'error':progress?'healthy':'checking';
 const status=error?'更新失败':!progress?busy?'正在检查':'待核查':'已接入';
 const counts=<p className="w-card-counts">昨日新增 <strong>{count??'—'}</strong> 条客资 · 累计入库 <strong>{progress?.totalAcquired??'—'}</strong> 条</p>;
 const routing=<p className="w-muted">高价值由人工跟进 · 中低价值由 AI 跟进{routes&&<>；人工 <strong>{routes.human}</strong> 条 · AI <strong>{routes.ai}</strong> 条 · 待评级 <strong>{routes.pending_rating}</strong> 条{routes.blocked>0&&<> · 禁止联系 <strong>{routes.blocked}</strong> 条</>}</>}</p>;
 const reason=error||(!progress?'正在读取获客入库记录。':progress.outboundPaused?'AI 跟进队列已分流，等待发送渠道接入。':'AI 跟进按客户价值分流，实际联系结果由发送渠道回传。');
 return <><div className={'w-capture w-card-status '+state+(expanded?' expanded':'')}>
 <button className="w-capture-summary" onClick={()=>setDetails(true)}><span className="w-health-dot"/><strong>主动获客AI</strong><span>客资入库与跟进</span><span>{status}</span><small>昨日新增 {count??'—'} 条客资</small></button>
 <button className="w-icon" aria-label={expanded?'收起主动获客AI详情':'展开主动获客AI详情'} aria-expanded={expanded} onClick={()=>setExpanded(!expanded)}>{expanded?<ChevronUp size={15}/>:<ChevronDown size={15}/>}</button>
 {expanded&&<div className="w-card-status-detail">{counts}{routing}<p className="w-muted">{reason}</p><small>最近入库：{progress?.lastAcquiredAt?date(progress.lastAcquiredAt,true):'暂无记录'}{progress&&<> · 昨日统计：{date(progress.statisticsDate)}（北京时间）</>}</small><div className="w-capture-actions">{openAcquisition&&<Button primary onClick={openAcquisition}>AI获得客资</Button>}<Button onClick={()=>setDetails(true)}>查看详情</Button><Button disabled={busy} onClick={()=>void check()}><RefreshCw size={14}/>{busy?'检查中…':'重新检查'}</Button></div></div>}
 </div>{details&&<Drawer title="主动获客AI · 客资与跟进" onClose={()=>setDetails(false)}><Notice>{reason}</Notice>{counts}{routing}<Facts items={[["昨日新增",count===undefined?'待核查':`${count} 条客资`],["累计入库",progress?`${progress.totalAcquired} 条`:'待核查'],["昨日高价值",values?`${values.high} 条`:'待核查'],["昨日中价值",values?`${values.medium} 条`:'待核查'],["昨日低价值",values?`${values.low} 条`:'待核查'],["昨日待评级",values?`${values.unrated} 条`:'待核查'],["统计日期",progress?`${progress.statisticsDate} · 北京时间`:'待核查'],["最近入库",progress?.lastAcquiredAt?date(progress.lastAcquiredAt,true):'暂无记录'],["最近检查",progress?.checkedAt?date(progress.checkedAt,true):'暂无记录']]}/><p className="w-muted">按北京时间昨日 00:00–24:00 的首次入库时间统计，同一条客资重复同步只计一次。S/A 为高价值，由人工跟进；B 为中价值，C/D 为低价值，由 AI 跟进。未评级先完成评级，拒绝联系的客户不进入发送队列。</p><div className="w-capture-actions"><Button onClick={()=>{setDetails(false);if(openAcquisition)openAcquisition();else source.native('Lead')}}>AI获得客资</Button><Button disabled={busy} onClick={()=>void check()}><RefreshCw size={14}/>{busy?'检查中…':'重新检查'}</Button></div></Drawer>}</>;
}
