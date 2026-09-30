export type Row = {id:string; name?:string; [key:string]:any};
export type Page = 'home'|'messages'|'customers'|'ai'|'knowledge';
export type Route = {page:Page; tab:string; id:string; entity:string};
export type Where = {type:string; attribute?:string; value?:unknown};
export const labels:Record<string,string>={new:'待人工回复',pending:'待人工回复',drafted:'AI 草稿待审核',waitingApproval:'AI 草稿待审核',readyToSend:'已审核 · 待发送',sending:'发送中',sent:'已发送',replied:'已回复',closed:'已处理',failed:'失败',received:'已接收',delivered:'已送达',mockSent:'模拟已发送',queued:'排队中',generated:'待审核',edited:'已修改',rejected:'已退回',stale:'待重新分析',online:'在线',offline:'离线',loginExpired:'登录失效',captcha:'需要验证码',claimed:'已领取',cancelled:'已取消',confirmed:'已确认',completed:'已完成',NotStarted:'未开始',Started:'进行中',Completed:'已完成',Canceled:'已取消',Deferred:'已延期',enabled:'启用',disabled:'停用',approved:'已审核',draft:'待审核',revoked:'已撤销',New:'新线索',Assigned:'已分配',InProcess:'跟进中',Converted:'已转化',Recycled:'待跟进',Dead:'无效'};
export const label=(x?:string)=>x?labels[x]||x:'未记录';
export const customerName=(r:Row)=>r.accountName||r.contactName||r.leadName||r.name||'未命名客户';
export const customerRef=(r:Row)=>r.accountId?{entity:'Account',id:r.accountId}:r.contactId?{entity:'Contact',id:r.contactId}:r.leadId?{entity:'Lead',id:r.leadId}:null;
export function origin(m:Row,demo=false){
 if(m.direction==='inbound')return `客户 · ${m.senderName||'姓名未记录'}`;
 // Only explicit demo fixtures carry verified attribution. Production never infers from control mode.
 if(demo && m.origin==='ai')return 'AI 自动回复';
 if(demo && m.origin==='assisted')return `业务员发送 · ${m.senderName} · AI 辅助起草`;
 if(demo && m.origin==='human')return `人工 · ${m.senderName}`;
 return `来源未确认${m.senderName?' · '+m.senderName:''}`;
}
export function date(value?:string,time=false){if(!value)return '未记录';const d=new Date(value.length===10?value:value.replace(' ','T')+(/Z$|[+-]\d\d:\d\d$/.test(value)?'':'Z'));return Number.isNaN(+d)?'时间待核对':new Intl.DateTimeFormat('zh-CN',{timeZone:'Asia/Shanghai',month:'2-digit',day:'2-digit',...(time?{hour:'2-digit',minute:'2-digit'}:{})}).format(d)}
export function certificateState(r:Row,now=new Date()){
 if(r.status==='revoked')return '已撤销';if(r.status!=='approved')return '待核对';if(!r.validTo)return '有效期待核对';
 if(r.validFrom && r.validFrom>new Intl.DateTimeFormat('sv-SE',{timeZone:'Asia/Shanghai'}).format(now))return '尚未生效';
 const today=new Intl.DateTimeFormat('sv-SE',{timeZone:'Asia/Shanghai'}).format(now);const diff=(Date.parse(r.validTo)-Date.parse(today))/86400000;
 return diff<0?'已过期':diff<=30?'即将到期':'有效';
}
export function readRoute():Route {const q=new URLSearchParams(location.search);const p=q.get('workspace')||'home';return {page:(['home','messages','customers','ai','knowledge'].includes(p)?p:'home') as Page,tab:q.get('tab')||'',id:q.get('record')||'',entity:q.get('entity')||'Account'}}
export function sortFollowups(rows:Row[]){return [...rows].sort((a,b)=>{const ad=a.dateEnd?Date.parse(a.dateEnd.replace(' ','T')+'Z'):Infinity;const bd=b.dateEnd?Date.parse(b.dateEnd.replace(' ','T')+'Z'):Infinity;return ad-bd||(('SABC'.indexOf(a.rating)>=0?'SABC'.indexOf(a.rating):4)-('SABC'.indexOf(b.rating)>=0?'SABC'.indexOf(b.rating):4))})}

// Source metadata describes files; it does not grant a downloadable URL.
export function attachmentInfo(metadata:any):{name:string;mediaType:string;size:string}[]{
 const items=Array.isArray(metadata)?metadata:metadata?.items||metadata?.files||[];
 if(!Array.isArray(items))return [];
 return items.filter(x=>x&&typeof x==='object').map(x=>({name:String(x.name||x.fileName||'附件'),mediaType:typeof x.mediaType==='string'?x.mediaType:'',size:Number.isFinite(x.size)&&x.size>=0?(x.size>=1024?(x.size/1024).toFixed(1)+' KB':x.size+' B'):''}));
}
