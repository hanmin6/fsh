import {useEffect,useState} from 'react';
import type {DataSource} from './bridge';
import type {Row,Where} from './domain';
import type {Props} from './work';
import {loadAllConversations} from './conversation-order';
import {categoryChannels,messageCategories,messageUnreadCounts,readMessageCategory,type MessageCategory} from './message-categories';
import {Button,Empty,Notice} from './ui';
import {Queue} from './queues';

export type ChannelDirectory={channels:Row[];loading:boolean;error:string};
async function loadChannels(source:DataSource){
 const rows=new Map<string,Row>();let offset=0;
 while(true){const result=await source.list('ExternalChannel',{limit:100,offset});if(!Array.isArray(result.list))throw Error('无法读取消息渠道');if(!result.list.length)break;const size=rows.size;result.list.forEach(r=>rows.set(r.id,r));if(size===rows.size)throw Error('消息渠道分页读取失败');offset+=result.list.length;if(result.total>=0?offset>=result.total:result.list.length<100)break;}
 return [...rows.values()];
}
export function useMessageDirectory(source:DataSource){
 const [directory,setDirectory]=useState<ChannelDirectory>({channels:[],loading:true,error:''});
 const [conversations,setConversations]=useState<Row[]|null>(null);
 const [counts,setCounts]=useState<Record<MessageCategory,number>|null>(null),[countsError,setCountsError]=useState(false),[revision,setRevision]=useState(0);
 useEffect(()=>{let active=true;setConversations(null);setDirectory({channels:[],loading:true,error:''});setCounts(null);setCountsError(false);
  loadChannels(source).then(async channels=>{if(!active)return;setDirectory({channels,loading:false,error:''});try{const records=await loadAllConversations(source,{});if(active){setCounts(messageUnreadCounts(channels,records.list));setConversations(records.list);}}catch{if(active)setCountsError(true)}}).catch(()=>{if(active){setDirectory({channels:[],loading:false,error:'无法读取消息渠道，请检查权限或重新加载。'});setCountsError(true)}});
  return()=>{active=false};
 },[source,revision]);
 useEffect(()=>{if(directory.loading||directory.error)return;let active=true;const timer=setInterval(async()=>{try{const records=await loadAllConversations(source,{});if(active){setCounts(messageUnreadCounts(directory.channels,records.list));setConversations(records.list);setCountsError(false)}}catch{if(active)setCountsError(true)}},60000);return()=>{active=false;clearInterval(timer)}},[source,directory]);
 return {directory,counts,countsError,conversations,refresh:()=>setRevision(v=>v+1)};
}
export function MessageQueue({directory,conversations,countsError,refresh,entity,...props}:{directory:ChannelDirectory;conversations:Row[]|null;countsError:boolean;refresh:()=>void;entity:string}&Props){
 const [category,setCategory]=useState<MessageCategory>('all');
 const channels=categoryChannels(directory.channels,category);
 const ids=new Set(channels.map(c=>c.id));
 const where:Where[]=category==='all'?[]:[{type:'in',attribute:entity==='OutboundTask'?'channelId':'conversationId',value:entity==='OutboundTask'?[...ids]:(conversations||[]).filter(c=>ids.has(c.channelId)).map(c=>c.id)}];
 const selector=<label>消息渠道<select aria-label="队列消息渠道" value={category} onChange={e=>setCategory(e.target.value as MessageCategory)}>{messageCategories.map(c=><option key={c.id} value={c.id}>{c.label}</option>)}</select></label>;
 if(directory.loading||directory.error)return <ChannelEmpty category={category} directory={directory} refresh={refresh}/>;
 if(category!=='all'&&entity==='AIReplyDraft'&&!conversations)return <section className="w-panel"><div className="w-toolbar">{selector}</div>{countsError?<Empty title="无法读取会话所属渠道" action={<Button onClick={refresh}>重试</Button>}/>:<div className="w-loading">正在读取渠道关联…</div>}</section>;
 if(category!=='all'&&(!channels.length||(entity==='AIReplyDraft'&&!(where[0].value as string[]).length)))return <section className="w-panel"><div className="w-toolbar">{selector}</div><Empty title="此渠道暂无对应记录" detail="渠道接入并产生审核或发送任务后，会显示在这里。"/></section>;
 return <Queue key={entity+category} {...props} entity={entity} extraWhere={where} toolbarExtra={selector}/>;
}
export function MessageNavigation({source,route,navigate,counts,countsError}:{counts:Record<MessageCategory,number>|null;countsError:boolean}&Pick<Props,'source'|'route'|'navigate'>){
 const category=readMessageCategory(route.tab),queue=['review','tasks'].includes(route.tab);
 return <div className="w-message-navigation">
  <div className="w-tabs" role="group" aria-label="消息分类">{messageCategories.map(c=><button key={c.id} aria-pressed={!queue&&category===c.id} className={!queue&&category===c.id?'active':''} onClick={()=>navigate('messages',{tab:c.id})}>{c.label}<span className="w-message-count" title={countsError?'未读数读取失败':counts?`${counts[c.id]} 条未读消息`:'正在读取未读数'}>未读 {countsError?'—':counts?counts[c.id]:'…'}</span></button>)}</div>
  <div className="w-message-operations" role="group" aria-label="消息处理">{category==='email'&&!queue&&!source.demo&&<Button disabled={!source.can('Email','read')} onClick={()=>source.native('Email')}>打开邮箱 · 写信</Button>}{[{id:'review',label:'待审核'},{id:'tasks',label:'发送任务'}].map(x=><button key={x.id} aria-pressed={route.tab===x.id} className={'w-button'+(route.tab===x.id?' active':'')} onClick={()=>navigate('messages',{tab:x.id})}>{x.label}</button>)}</div>
 </div>;
}
export function ChannelEmpty({category,directory,refresh}:{category:MessageCategory;directory:ChannelDirectory;refresh:()=>void}){
 if(directory.loading)return <div className="w-loading" role="status">正在读取消息渠道…</div>;
 if(directory.error)return <Empty title="暂时无法显示消息渠道" detail={directory.error} action={<Button onClick={refresh}>重试</Button>}/>;
 const channels=categoryChannels(directory.channels,category),name=messageCategories.find(c=>c.id===category)?.label||'消息';
 if(channels.length)return null;
 return <section className="w-panel w-channel-empty"><Notice>{name} · 待接入</Notice><Empty title={category==='email'?'邮件渠道待接入':category==='social'?'社交渠道待接入':'平台渠道待接入'} detail={category==='email'?'Zoho 邮箱接通收发同步后，客户邮件会集中显示在这里。':category==='social'?'社交账号接通并回传消息后，会显示客户会话、来源与处理状态。':'接通平台并同步消息后，客户会话会显示在这里。'} action={<Button onClick={refresh}>重新检查接入状态</Button>}/></section>;
}
