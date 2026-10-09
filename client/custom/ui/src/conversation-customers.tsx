import {useEffect,useState} from 'react';
import type {DataSource,ListOptions} from './bridge';
import {customerRef,type Row} from './domain';
import {Badge,Rating} from './ui';

type CustomerResult={row?:Row;error?:string};
export type ConversationCustomers=Record<string,CustomerResult>;
const refKey=(ref:{entity:string;id:string})=>ref.entity+'/'+ref.id;

/** Resolve grades from customer records; conversations do not own a rating. */
export function useConversationCustomers(source:DataSource,conversations:Row[]):ConversationCustomers{
 const refs=new Map(conversations.flatMap(row=>{const ref=customerRef(row);return ref?[[refKey(ref),ref] as const]:[]}));
 const key=JSON.stringify([...refs.values()].sort((a,b)=>refKey(a).localeCompare(refKey(b))));
 const [result,setResult]=useState<{key:string;customers:ConversationCustomers}>({key:'',customers:{}});
 const [revision,setRevision]=useState(0);
 useEffect(()=>{
  let active=true;
  const groups=new Map<string,string[]>();
  for(const ref of JSON.parse(key) as {entity:string;id:string}[]){const ids=groups.get(ref.entity)||[];ids.push(ref.id);groups.set(ref.entity,ids)}
  const subscriptions:(()=>void)[]=[];
  const batches=[...groups].flatMap(([entity,ids])=>Array.from({length:Math.ceil(ids.length/100)},(_,index)=>[entity,ids.slice(index*100,(index+1)*100)] as const));
  const requests=batches.map(async([entity,ids])=>{
   const options:ListOptions={where:[{type:'in',attribute:'id',value:ids}],limit:ids.length};
   if(!source.can(entity,'read'))return Object.fromEntries(ids.map(id=>[entity+'/'+id,{error:'无评级权限'}]));
   const cacheKey=source.cacheKey?.('list',entity,options);
   if(cacheKey&&source.subscribe)subscriptions.push(source.subscribe(cacheKey,()=>{if(active)setRevision(v=>v+1)}));
   for(const id of ids){
    const recordKey=source.cacheKey?.('record',entity,id);
    if(recordKey&&source.subscribe)subscriptions.push(source.subscribe(recordKey,()=>{if(active)setRevision(v=>v+1)}));
   }
   try{
    const data=await source.list(entity,options);const rows=new Map(data.list.map(row=>[row.id,row]));
    return Object.fromEntries(ids.map(id=>[entity+'/'+id,rows.has(id)?{row:rows.get(id)}:{error:'评级读取失败'}]));
   }catch{return Object.fromEntries(ids.map(id=>[entity+'/'+id,{error:'评级读取失败'}]))}
  });
  Promise.all(requests).then(values=>{if(active)setResult({key,customers:Object.assign({},...values)})});
  return()=>{active=false;subscriptions.forEach(unsubscribe=>unsubscribe())};
 },[source,key,revision]);
 return result.key===key?result.customers:{};
}

export function ConversationRating({conversation,customers}:{conversation:Row;customers:ConversationCustomers}){
 const ref=customerRef(conversation);
 if(!ref)return <Badge tone="neutral">未关联客户</Badge>;
 const result=customers[refKey(ref)];
 if(result?.row)return <Rating value={result.row.rating}/>;
 return <Badge tone="neutral">{result?.error||'读取评级…'}</Badge>;
}
