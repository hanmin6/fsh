import {useEffect,useRef,useState} from 'react';
import {ChevronDown,ChevronUp,RefreshCw} from 'lucide-react';
import type {DataSource} from './bridge';
import {date} from './domain';
import {Button,Drawer,Facts,Notice} from './ui';

type Progress={date:string;dailyTarget:number;todayCompleted:number;remaining:number;lastSentAt:string|null;checkedAt:string;connected:boolean;lastCheckAt:string|null};

export function CardStatus({source,revision}:{source:DataSource;revision:number}){
 const [savedProgress,setProgress]=useState<Progress|null>(null),[busy,setBusy]=useState(false),[error,setError]=useState(''),[expanded,setExpanded]=useState(true),[details,setDetails]=useState(false);
 const inFlight=useRef(false),sequence=useRef(0);
 const today=new Intl.DateTimeFormat('sv-SE',{timeZone:'Asia/Shanghai'}).format(new Date());
 const progress=savedProgress?.date===today?savedProgress:null;
 const check=async()=>{if(inFlight.current)return;inFlight.current=true;const request=++sequence.current;setBusy(true);try{const next=await source.get('Fusanhe/card-status');if(!Number.isInteger(next.todayCompleted)||next.todayCompleted<0||next.dailyTarget!==15)throw Error('invalid status');if(sequence.current===request){setProgress(next);setError('')}}catch{if(sequence.current===request)setError('进度更新失败，请重新检查。')}finally{if(sequence.current===request){inFlight.current=false;setBusy(false)}}};
 useEffect(()=>{setProgress(null);setError('');inFlight.current=false;void check();return()=>{sequence.current++;inFlight.current=false}},[source]);
 useEffect(()=>{if(revision)void check()},[revision]);
 const count=progress?.todayCompleted,target=progress?.dailyTarget||15;
 const state=error?'error':progress&&(progress.connected||progress.todayCompleted>=target)?'healthy':'checking';
 const status=error?'更新失败':!progress?busy?'正在检查':'待核查':progress.todayCompleted>=target?'今日已完成':progress.connected?'已连接':'待连接';
 const counts=<p className="w-card-counts">每日目标 <strong>{target}</strong> 个客户 · 今日已联系 <strong>{count??'—'}</strong> 个{progress&&<> · 还差 <strong>{progress.remaining}</strong> 个</>}</p>;
 const reason=error||(!progress?'正在读取今日触达记录。':progress.todayCompleted>=target?'今日 15 个客户的目标已完成。':progress.connected?'获客 AI 已连接，完成触达后自动更新进度。':'等待获客 AI 连接，完成触达后自动更新进度。');
 return <><div className={'w-capture w-card-status '+state+(expanded?' expanded':'')}>
 <button className="w-capture-summary" onClick={()=>setDetails(true)}><span className="w-health-dot"/><strong>主动获客AI</strong><span>客户联系信息</span><span>{status}</span><small>今日已联系 {count??'—'} / {target} 个客户</small></button>
 <button className="w-icon" aria-label={expanded?'收起主动获客AI详情':'展开主动获客AI详情'} aria-expanded={expanded} onClick={()=>setExpanded(!expanded)}>{expanded?<ChevronUp size={15}/>:<ChevronDown size={15}/>}</button>
 {expanded&&<div className="w-card-status-detail">{counts}<p className="w-muted">{reason}</p><small>最近联系：{progress?.lastSentAt?date(progress.lastSentAt,true):'暂无记录'}{progress&&<> · 统计日期：{date(progress.date)}（北京时间）</>}</small><div className="w-capture-actions"><Button onClick={()=>setDetails(true)}>查看详情</Button><Button disabled={busy} onClick={()=>void check()}><RefreshCw size={14}/>{busy?'检查中…':'重新检查'}</Button></div></div>}
 </div>{details&&<Drawer title="主动获客AI · 今日进度" onClose={()=>setDetails(false)}><Notice>{reason}</Notice>{counts}<Facts items={[["每日目标",`${target} 个客户`],["今日已联系",count===undefined?'待核查':`${count} 个客户`],["今日还差",progress?`${progress.remaining} 个客户`:'待核查'],["统计日期",progress?`${progress.date} · 北京时间`:'待核查'],["最近联系",progress?.lastSentAt?date(progress.lastSentAt,true):'暂无记录'],["最近检查",progress?.checkedAt?date(progress.checkedAt,true):'暂无记录']]}/><p className="w-muted">按北京时间每天重新统计；同一客户多次触达只计 1 个。仅计入获客 AI 已成功发送或送达的记录，草稿、排队、失败及模拟发送不计入。</p><Button disabled={busy} onClick={()=>void check()}><RefreshCw size={14}/>{busy?'检查中…':'重新检查'}</Button></Drawer>}</>;
}
