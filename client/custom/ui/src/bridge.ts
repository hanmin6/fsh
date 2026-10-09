import type {Row,Where} from './domain';

export interface HostBridge {
 get(path:string,params?:Record<string,unknown>):Promise<any>;
 post(path:string,data:Record<string,unknown>):Promise<any>;
 patch(path:string,data:Record<string,unknown>):Promise<any>;
 can(entity:string,action?:string):boolean;
 native(entity:string,id?:string,action?:string):void;
 user:{id:string;name:string};
}

export type ListOptions={search?:string;where?:Where[];offset?:number;orderBy?:string;order?:string;limit?:number};
export type Result={list:Row[];total:number;fromCache?:boolean;syncing?:boolean};
export type CacheListener=()=>void;
export interface DataSource extends HostBridge {
 demo:boolean;
 list(entity:string,options?:ListOptions):Promise<Result>;
 cacheKey?(kind:'list'|'record',entity:string,idOrOptions:string|ListOptions):string;
 subscribe?(key:string,listener:CacheListener):()=>void;
}
export class DataError extends Error {}

export function liveSource(host:HostBridge):DataSource{return {...host,demo:false,async list(entity,options={}){
 if(!host.can(entity,'read'))throw new DataError('没有读取权限，请联系维护人员。');
 try {return await host.get(entity,{maxSize:options.limit||30,offset:options.offset||0,orderBy:options.orderBy||'createdAt',order:options.order||'desc',...(options.search?{textFilter:options.search}:{}),where:options.where||[]});}
 catch(e:any){throw new DataError(e.status===403?'此模块没有访问权限或尚未启用。':e.status===404?'此模块尚未部署。':'数据加载失败，请重试。');}
}}}

const CACHE_DB='fusanhe-workspace-cache';
const CACHE_STORE='records';
const CACHE_ENTITIES=new Set(['Account','Contact','Lead','ExternalConversation','ExternalMessage']);
type CacheEntry={key:string;userId:string;entity:string;kind:'list'|'record';value:any;cursor?:string;updatedAt:number};
const memoryCache=new Map<string,CacheEntry>();
const listeners=new Map<string,Set<CacheListener>>();
const syncs=new Map<string,Promise<void>>();
let database:Promise<IDBDatabase|null>|null=null;

function openDatabase(){
 if(database)return database;
 database=new Promise(resolve=>{
  if(typeof indexedDB==='undefined'){resolve(null);return;}
  try {
   const request=indexedDB.open(CACHE_DB,1);
   request.onupgradeneeded=()=>{if(!request.result.objectStoreNames.contains(CACHE_STORE))request.result.createObjectStore(CACHE_STORE,{keyPath:'key'});};
   request.onsuccess=()=>resolve(request.result);
   request.onerror=()=>resolve(null);
  } catch {resolve(null)}
 });
 return database;
}
async function readCache(key:string){
 const local=memoryCache.get(key);if(local)return local;
 const db=await openDatabase();if(!db)return undefined;
 return await new Promise<CacheEntry|undefined>(resolve=>{try{const request=db.transaction(CACHE_STORE,'readonly').objectStore(CACHE_STORE).get(key);request.onsuccess=()=>{const value=request.result as CacheEntry|undefined;if(value)memoryCache.set(key,value);resolve(value)};request.onerror=()=>resolve(undefined)}catch{resolve(undefined)}});
}
async function writeCache(entry:CacheEntry){
 memoryCache.set(entry.key,entry);
 const db=await openDatabase();if(!db)return;
 await new Promise<void>(resolve=>{try{const request=db.transaction(CACHE_STORE,'readwrite').objectStore(CACHE_STORE).put(entry);request.onsuccess=()=>resolve();request.onerror=()=>resolve()}catch{resolve()}});
}
function notify(key:string){listeners.get(key)?.forEach(listener=>listener())}
function subscribe(key:string,listener:CacheListener){let set=listeners.get(key);if(!set){set=new Set();listeners.set(key,set)}set.add(listener);return()=>{set!.delete(listener);if(!set!.size)listeners.delete(key)}}
function stableOptions(options:ListOptions){return {search:options.search||'',where:options.where||[],offset:options.offset||0,orderBy:options.orderBy||'createdAt',order:options.order||'desc',limit:options.limit||30}}
function maxCursor(rows:Row[],fallback?:string){let cursor=fallback;for(const row of rows){const value=row.modifiedAt||row.updatedAt||row.lastMessageAt||row.sentAt||row.createdAt;if(value&&(!cursor||String(value)>String(cursor)))cursor=String(value)}return cursor}
function sortRows(rows:Row[],options:ListOptions){const field=options.orderBy||'createdAt';const direction=options.order==='asc'?1:-1;return [...rows].sort((a,b)=>String(a[field]??'').localeCompare(String(b[field]??''),undefined,{numeric:true})*direction)}
function sameRows(a:Row[],b:Row[]){return JSON.stringify(a)===JSON.stringify(b)}
function cacheKeyFor(userId:string,kind:'list'|'record',entity:string,idOrOptions:string|ListOptions){return `${userId}|${kind}|${entity}|${typeof idOrOptions==='string'?idOrOptions:JSON.stringify(stableOptions(idOrOptions))}`}
function serverError(e:any){return new DataError(e?.status===403?'此模块没有访问权限或尚未启用。':e?.status===404?'此模块尚未部署。':'数据加载失败，请重试。')}

/** A local-first source for the entities users revisit most often. */
export function cachedSource(host:HostBridge):DataSource{
 const base=liveSource(host);const userId=host.user.id||'anonymous';
 const keyOf=(kind:'list'|'record',entity:string,idOrOptions:string|ListOptions)=>cacheKeyFor(userId,kind,entity,idOrOptions);
 const invalidate=async(entity:string)=>{
  const affected=[...memoryCache.values()].filter(entry=>entry.userId===userId&&entry.entity===entity);
  for(const entry of affected)memoryCache.delete(entry.key);
  const db=await openDatabase();if(!db){for(const entry of affected)notify(entry.key);return}
  await new Promise<void>(resolve=>{try{const request=db.transaction(CACHE_STORE,'readwrite').objectStore(CACHE_STORE).openCursor();request.onsuccess=()=>{const cursor=request.result as IDBCursorWithValue|null;if(!cursor){resolve();return}const value=cursor.value as CacheEntry;if(value.userId===userId&&value.entity===entity)cursor.delete();cursor.continue()};request.onerror=()=>resolve()}catch{resolve()}});
  for(const entry of affected)notify(entry.key);
 };
 const refreshList=async(key:string,entity:string,options:ListOptions,entry?:CacheEntry)=>{
  if(syncs.has(key))return syncs.get(key)!;
  const promise=(async()=>{
   try {
    const incremental=Boolean(entry?.cursor)&&!((options.offset||0)>0);
    const where=[...(options.where||[]),...(incremental?[{type:'greaterThan',attribute:'modifiedAt',value:entry!.cursor} as Where]:[])];
    const result=await base.list(entity,{...options,offset:incremental?0:options.offset,limit:incremental?Math.max(options.limit||30,100):options.limit,where});
    const previous=entry?.value as Result|undefined;let merged=result.list;
    if(incremental&&previous){const byId=new Map(previous.list.map(row=>[row.id,row]));for(const row of result.list)byId.set(row.id,row);merged=sortRows([...byId.values()],options)}
    const next:CacheEntry={key,userId,entity,kind:'list',value:{list:merged,total:Math.max(result.total,previous?.total||0,merged.length)},cursor:maxCursor(merged,entry?.cursor),updatedAt:Date.now()};
    const changed=!previous||!sameRows(previous.list,next.value.list)||previous.total!==next.value.total;
    await writeCache(next);if(changed)notify(key);
   } catch { /* Keep the last good cache when the network is unavailable. */ }
  })().finally(()=>syncs.delete(key));
  syncs.set(key,promise);return promise;
 };
 const source:DataSource={...base,
  cacheKey:(kind,entity,idOrOptions)=>keyOf(kind,entity,idOrOptions),subscribe,
  async list(entity,options={}){
   if(!CACHE_ENTITIES.has(entity))return base.list(entity,options);
   if(!host.can(entity,'read'))throw new DataError('没有读取权限，请联系维护人员。');
   const key=keyOf('list',entity,options);const entry=await readCache(key);
   if(entry?.value){void refreshList(key,entity,options,entry);return {...entry.value,fromCache:true,syncing:true} as Result;}
   try {const result=await base.list(entity,options);await writeCache({key,userId,entity,kind:'list',value:result,cursor:maxCursor(result.list),updatedAt:Date.now()});return result;}
   catch(e){throw serverError(e)}
  },
  async get(path,params={}){
   const [entity,id]=path.split('/');if(!id||!CACHE_ENTITIES.has(entity))return base.get(path,params);
   if(!host.can(entity,'read'))throw new DataError('没有读取权限，请联系维护人员。');
   const key=keyOf('record',entity,id);const entry=await readCache(key);
   const sync=async()=>{try{const value=await base.get(path,params);const previous=entry?.value;await writeCache({key,userId,entity,kind:'record',value,cursor:maxCursor([value],entry?.cursor),updatedAt:Date.now()});if(JSON.stringify(previous)!==JSON.stringify(value))notify(key)}catch{}};
   if(entry?.value){void sync();return entry.value;}
   try{const value=await base.get(path,params);await writeCache({key,userId,entity,kind:'record',value,cursor:maxCursor([value]),updatedAt:Date.now()});return value}catch(e){throw serverError(e)}
  },
  async post(path,data){
   const result=await base.post(path,data);
   if(/^Fusanhe\/conversation\/[^/]+\/translate$/.test(path)&&Array.isArray(result?.messages)){
    const translations=new Map<string,string>(result.messages.filter((r:any)=>r.status==='completed'&&typeof r.translatedBody==='string').map((r:any)=>[r.id,r.translatedBody]));
    // Update loaded caches without resetting a timeline that has paged into older history.
    for(const entry of [...memoryCache.values()]){
     if(entry.userId!==userId||entry.entity!=='ExternalMessage')continue;
     const update=(row:Row)=>translations.has(row.id)?{...row,translatedBody:translations.get(row.id)}:row;
     const value=entry.kind==='list'?{...entry.value,list:entry.value.list.map(update)}:update(entry.value);
     if(JSON.stringify(value)!==JSON.stringify(entry.value))await writeCache({...entry,value});
    }
   }
   return result;
  },
  async patch(path,data){const result=await base.patch(path,data);const entity=path.split('/')[0];if(CACHE_ENTITIES.has(entity))await invalidate(entity);return result;}
 };
 return source;
}
