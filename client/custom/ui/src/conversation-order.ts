import {useEffect,useState} from 'react';
import type {DataSource,ListOptions,Result} from './bridge';
import {customerRef,type Row} from './domain';
import {useConversationCustomers,type ConversationCustomers} from './conversation-customers';

export type ConversationOrder='rating'|'latest';
export function sortConversationsByRating(rows:Row[],customers:ConversationCustomers):Row[]{
 const rank=(row:Row)=>{const ref=customerRef(row);const rating=ref?customers[ref.entity+'/'+ref.id]?.row?.rating:undefined;const index=['S','A','B','C','D'].indexOf(rating||'');return index>=0?index:5};
 return [...rows].sort((a,b)=>rank(a)-rank(b)||String(b.lastMessageAt||'').localeCompare(String(a.lastMessageAt||''))||a.id.localeCompare(b.id));
}

/** Read the full filtered set before sorting, so later pages can contain top grades. */
export async function loadAllConversations(source:DataSource,options:ListOptions):Promise<Result>{
 if(!source.can('ExternalConversation','read'))throw new Error('没有读取权限，请联系维护人员。');
 const rows=new Map<string,Row>();let offset=0;
 while(true){
  const page=source.demo?await source.list('ExternalConversation',{...options,limit:100,offset}):await source.get('ExternalConversation',{maxSize:100,offset,orderBy:'lastMessageAt',order:'desc',where:options.where||[],...(options.search?{textFilter:options.search}:{})});
  if(!Array.isArray(page.list))throw new Error('会话加载失败，请重试。');
  if(!page.list.length)break;
  const size=rows.size;for(const row of page.list)rows.set(row.id,row);
  if(rows.size===size)throw new Error('会话分页读取失败，请重试。');
  offset+=page.list.length;
  if(typeof page.total==='number'&&page.total>=0?offset>=page.total:page.list.length<100)break;
 }
 return {list:[...rows.values()],total:rows.size};
}

export function useMessageConversations(source:DataSource,options:ListOptions,order:ConversationOrder,enabled=true){
 const key=JSON.stringify({...options,offset:order==='rating'?0:options.offset});
 const [data,setData]=useState<Result>({list:[],total:0}),[loading,setLoading]=useState(true),[error,setError]=useState(''),[revision,setRevision]=useState(0);
 useEffect(()=>{
  let active=true;if(!enabled){setLoading(false);setError('');setData({list:[],total:0});return}setLoading(true);setError('');const parsed=JSON.parse(key);
  const cacheKey=order==='latest'?source.cacheKey?.('list','ExternalConversation',parsed):undefined;
  const unsubscribe=cacheKey&&source.subscribe?source.subscribe(cacheKey,()=>{if(active)setRevision(v=>v+1)}):undefined;
  const request=order==='rating'?loadAllConversations(source,parsed):source.list('ExternalConversation',parsed);
  request.then(value=>{if(active)setData(value)}).catch(()=>{if(active){setData({list:[],total:0});setError('会话加载失败，请重试。')}}).finally(()=>{if(active)setLoading(false)});
  return()=>{active=false;unsubscribe?.()};
 },[source,key,order,revision,enabled]);
 const idsKey=JSON.stringify(data.list.map(row=>row.id));
 useEffect(()=>{
  if(order!=='rating'||!source.cacheKey||!source.subscribe)return;
  const subscriptions=(JSON.parse(idsKey) as string[]).map(id=>source.subscribe!(source.cacheKey!('record','ExternalConversation',id),()=>setRevision(v=>v+1)));
  return()=>subscriptions.forEach(unsubscribe=>unsubscribe());
 },[source,order,idsKey]);
 const customers=useConversationCustomers(source,data.list);
 const ratingLoading=order==='rating'&&data.list.some(row=>{const ref=customerRef(row);return ref&&!customers[ref.entity+'/'+ref.id]});
 const rows=order==='rating'?sortConversationsByRating(data.list,customers).slice(options.offset||0,(options.offset||0)+(options.limit||30)):data.list;
 return {...data,list:rows,customers,loading:loading||ratingLoading,error,refresh:()=>setRevision(v=>v+1)};
}
