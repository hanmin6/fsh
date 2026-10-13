import {useState} from 'react';
import {RefreshCw} from 'lucide-react';
import type {Props} from './work';
import {date,label,type Where} from './domain';
import {Avatar,Badge,Button,Paging,Rating,SearchBox,State,useList} from './ui';

const sources=['Muse','Xpoz','OpenOutreach'];
const routes:Record<string,string>={human:'人工跟进',ai:'AI 跟进',pending_rating:'待评级',blocked:'禁止联系'};
// Legacy imports use Muse as the ingest system and preserve the provider in their source ID.
const provider=(system:string,id:string)=>system==='Muse'&&id?.startsWith('xpoz:')?'Xpoz':system==='Muse'&&id?.startsWith('openoutreach:')?'OpenOutreach':system;
function sourceFilter(origin:string):Where[]{
 if(!origin)return [];
 if(origin==='Muse')return [{type:'equals',attribute:'fusanheSourceSystem',value:'Muse'},{type:'notContains',attribute:'fusanheSourceId',value:'xpoz:'},{type:'notContains',attribute:'fusanheSourceId',value:'openoutreach:'}];
 return [{type:'or',value:[{type:'equals',attribute:'fusanheSourceSystem',value:origin},{type:'and',value:[{type:'equals',attribute:'fusanheSourceSystem',value:'Muse'},{type:'startsWith',attribute:'fusanheSourceId',value:origin.toLowerCase()+':'}]}]}];
}

export function AcquisitionPage({source,navigate}:Props){
 const [search,setSearch]=useState(''),[origin,setOrigin]=useState(''),[rating,setRating]=useState(''),[route,setRoute]=useState(''),[offset,setOffset]=useState(0);
 const where:Where[]=[
  {type:'in',attribute:'fusanheSourceSystem',value:sources},
  {type:'isNotNull',attribute:'fusanheSourceId'},
  {type:'notEquals',attribute:'fusanheSourceId',value:''},
  ...sourceFilter(origin),
  ...(rating?[{type:'equals',attribute:'rating',value:rating}]:[]),
  ...(route?[{type:'equals',attribute:'fusanheFollowUpRoute',value:route}]:[]),
 ];
 const data=useList(source,'Lead',{search,offset,where,orderBy:'createdAt',order:'desc',limit:30});
 const change=(set:(value:string)=>void,value:string)=>{set(value);setOffset(0)};
 const filtered=!!(search||origin||rating||route);
 const clear=()=>{setSearch('');setOrigin('');setRating('');setRoute('');setOffset(0)};
 const open=(id:string)=>navigate('customers',{entity:'Lead',id});
 return <section className="w-panel" aria-label="AI获得客资列表">
  <div className="w-toolbar">
   <SearchBox value={search} onChange={v=>change(setSearch,v)} placeholder="搜索客资、公司或邮箱"/>
   <label>来源<select aria-label="客资来源" value={origin} onChange={e=>change(setOrigin,e.target.value)}><option value="">全部来源</option>{sources.map(x=><option key={x}>{x}</option>)}</select></label>
   <label>评级<select aria-label="客资评级" value={rating} onChange={e=>change(setRating,e.target.value)}><option value="">全部评级</option>{Object.entries({S:'超高',A:'高',B:'中',C:'低',D:'超低'}).map(([v,text])=><option key={v} value={v}>{text}</option>)}</select></label>
   <label>跟进分流<select aria-label="客资跟进分流" value={route} onChange={e=>change(setRoute,e.target.value)}><option value="">全部分流</option>{Object.entries(routes).map(([v,text])=><option key={v} value={v}>{text}</option>)}</select></label>
   {filtered&&<Button onClick={clear}>清除筛选</Button>}
   <Button disabled={data.loading} onClick={data.refresh}><RefreshCw size={14}/>刷新客资</Button>
  </div>
  <div className="w-inline-note">S/A 由人工跟进，B/C/D 由 AI 跟进；未评级先完成评级。跟进分流表示处理安排，实际触达与回复请在客户资料中查看。</div>
  <State state={data} emptyTitle={filtered?'没有匹配的 AI 客资':'暂无 AI 获得的客资'} emptyDetail={filtered?'调整来源、评级或跟进分流筛选。':'AI 获取并入库的客户线索会显示在这里。'} emptyAction={filtered?<Button onClick={clear}>清除筛选</Button>:undefined}>
   <div className="w-table-wrap"><table><thead><tr>{['客户 / 公司','来源','价值评级','跟进分流','客户阶段','入库时间','操作'].map(x=><th key={x}>{x}</th>)}</tr></thead><tbody>
    {data.list.map(r=><tr key={r.id}>
     <td><button className="w-customer-name" onClick={()=>open(r.id)}><Avatar name={r.name} small/><span><strong>{r.accountName||r.aiCompanyName||r.name||'未命名客户'}</strong><small>{r.emailAddress||(r.accountName&&r.accountName!==r.name?r.name:'联系方式待补充')}</small></span></button></td>
     <td>{provider(r.fusanheSourceSystem,r.fusanheSourceId)}</td>
     <td><Rating value={r.rating}/><small className="w-rating-state">{r.ratingSource==='manual'?'人工确认':r.aiRatingStatus==='completed'?'AI 自动评级':'评级待核实'}</small></td>
     <td><Badge tone={r.fusanheFollowUpRoute==='blocked'?'danger':''}>{routes[r.fusanheFollowUpRoute]||'待分流'}</Badge></td>
     <td>{label(r.status)}</td><td>{date(r.createdAt,true)}</td><td><button className="w-link" onClick={()=>open(r.id)}>查看资料</button></td>
    </tr>)}
   </tbody></table></div>
  </State>
  {!data.error&&<Paging offset={offset} total={data.total} onChange={setOffset}/>}
 </section>;
}
