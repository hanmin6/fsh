import {useEffect,useRef,useState} from 'react';
import type {DataSource} from './bridge';
import type {Row} from './domain';

type Translation={body:string;status:'queued'|'loading'|'completed'|'skipped'|'failed'|'busy';translatedBody?:string;errorCode?:string};
export function translationCandidate(body:unknown):boolean{
 return typeof body==='string'&&/[a-z]{2}/i.test(body.replace(/https?:\/\/\S+|[\w.+-]+@[\w.-]+\.[a-z]{2,}/gi,''));
}

/** One queue per open conversation. Body snapshots protect against stale responses. */
export function useMessageTranslations(source:DataSource,conversationId:string,messages:Row[]){
 const [states,setStates]=useState<Record<string,Translation>>({});
 const jobs=useRef(new Map<string,Translation>()),latest=useRef(messages),alive=useRef(false),running=useRef<number|null>(null),generation=useRef(0),timers=useRef(new Set<ReturnType<typeof setTimeout>>()),busyChecks=useRef(new Map<string,number>()),retryIds=useRef(new Set<string>());
 latest.current=messages;
 useEffect(()=>{generation.current++;alive.current=true;jobs.current.clear();retryIds.current.clear();busyChecks.current.clear();setStates({});return()=>{alive.current=false;generation.current++;for(const timer of timers.current)clearTimeout(timer);timers.current.clear()}},[source,conversationId]);
 const publish=()=>{if(alive.current)setStates(Object.fromEntries(jobs.current))};
 const pump=async()=>{
  const version=generation.current;
  if(running.current===version||!alive.current)return;
  running.current=version;
  try{
   while(alive.current&&generation.current===version){
    const batch:Row[]=[];let bytes=0;
    for(const m of latest.current){
     const job=jobs.current.get(m.id);
     if(job?.status!=='queued'||job.body!==m.body||m.translatedBody)continue;
     const size=new TextEncoder().encode(m.body).length;
     if(batch.length&&(batch.length>=6||bytes+size>12000))break;
     batch.push(m);bytes+=size;
    }
    if(!batch.length)break;
    const retry=batch.some(m=>retryIds.current.has(m.id));
    for(const m of batch){jobs.current.set(m.id,{body:m.body,status:'loading'});retryIds.current.delete(m.id)}
    publish();
    try{
     const response=await source.post('Fusanhe/conversation/'+encodeURIComponent(conversationId)+'/translate',{messageIds:batch.map(m=>m.id),...(retry?{retry:true}:{})});
     if(!alive.current||generation.current!==version)return;
     const values=new Map<string,any>();
     if(Array.isArray(response?.messages))for(const value of response.messages){if(!values.has(value.id))values.set(value.id,value);else values.set(value.id,null)}
     for(const m of batch){
      if(jobs.current.get(m.id)?.body!==m.body)continue;
      const value=values.get(m.id),valid=value&&['completed','skipped','failed','busy'].includes(value.status)&&(value.status!=='completed'||typeof value.translatedBody==='string'&&value.translatedBody.trim());
      jobs.current.set(m.id,valid?{body:m.body,status:value.status,translatedBody:value.translatedBody,errorCode:value.errorCode}:{body:m.body,status:'failed'});
      if(valid&&value.status==='busy'&&(busyChecks.current.get(m.id)||0)<12){
       busyChecks.current.set(m.id,(busyChecks.current.get(m.id)||0)+1);
       const timer=setTimeout(()=>{timers.current.delete(timer);if(!alive.current||generation.current!==version)return;const job=jobs.current.get(m.id);if(job&&job.body===m.body&&job.status==='busy'){jobs.current.set(m.id,{body:m.body,status:'queued'});publish();void pump()}},5000);timers.current.add(timer);
      }
     }
    }catch{
     if(!alive.current||generation.current!==version)return;
     for(const m of batch)if(jobs.current.get(m.id)?.body===m.body)jobs.current.set(m.id,{body:m.body,status:'failed'});
    }
    publish();
   }
  }finally{if(running.current===version)running.current=null}
 };
 useEffect(()=>{
  for(const m of messages){
   const job=jobs.current.get(m.id);
   if(m.translatedBody){jobs.current.set(m.id,{body:m.body,status:'completed',translatedBody:m.translatedBody});continue}
   if(translationCandidate(m.body)&&(!job||job.body!==m.body))jobs.current.set(m.id,{body:m.body,status:'queued'});
  }
  publish();void pump();
 },[source,conversationId,messages]);
 return {states,retry:(message:Row)=>{jobs.current.set(message.id,{body:message.body,status:'queued'});retryIds.current.add(message.id);publish();void pump()}};
}

export function MessageTranslation({message,state,retry}:{message:Row;state?:Translation;retry:()=>void}){
 const translation=message.translatedBody||(state?.body===message.body&&state?.translatedBody);
 if(translation)return <div className="w-translation"><small>中文译文</small><p>{translation}</p></div>;
 if(!state||state.body!==message.body||state.status==='skipped')return null;
 if(state.status==='queued'||state.status==='loading')return <div className="w-translation-status" role="status">正在翻译为中文…</div>;
 if(state.status==='failed'||state.status==='busy')return <div className="w-translation-status"><span>{state.status==='busy'?'翻译正在处理中':state.errorCode==='translation_message_too_large'?'消息过长，暂无法自动翻译':'翻译失败，原文可正常查看'}</span><button className="w-link" onClick={retry}>重试翻译</button></div>;
 return null;
}
