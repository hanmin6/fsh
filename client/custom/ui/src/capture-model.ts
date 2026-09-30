import type {Row} from './domain';
export type Capture={type:string;name:string;state:'healthy'|'error'|'checking';lastSuccessAt:string|null;lastCheckAt:string|null;reason:string;key:string;channels:Row[];agents:Row[]};
export const platforms=[{type:'MadeInChina',name:'Made-in-China'},{type:'Alibaba',name:'阿里国际站'}];
export function timestamp(value?:string|null){if(!value)return NaN;return Date.parse(value.replace(' ','T')+(/Z$|[+-]\d\d:\d\d$/.test(value)?'':'Z'))}
export function assessCapture(type:string,channels:Row[],agents:Row[],now=Date.now()):Capture{
 const name=platforms.find(p=>p.type===type)?.name||type;
 const rows=channels.filter(c=>c.type===type&&c.enabled!==false);
 const workers=agents.filter(a=>a.mode==='real'&&Array.isArray(a.capabilities)&&a.capabilities.includes(type));
 const successes=rows.map(c=>c.captureLastSuccessAt||c.lastSyncAt).filter(v=>Number.isFinite(timestamp(v))&&timestamp(v)<=now+60000).sort((a,b)=>timestamp(b)-timestamp(a));
 const checks=workers.map(a=>a.lastHeartbeatAt).filter(v=>Number.isFinite(timestamp(v))&&timestamp(v)<=now+60000).sort((a,b)=>timestamp(b)-timestamp(a));
 const lastSuccessAt=successes[0]||null,lastCheckAt=checks[0]||null;
 const errors=workers.filter(a=>a.status!=='online'||!Number.isFinite(timestamp(a.lastHeartbeatAt))||now-timestamp(a.lastHeartbeatAt)>5*60000);
 const error=rows.find(c=>['offline','degraded'].includes(c.connectionStatus));
 let reason='',state:Capture['state']='checking';
 if(error||errors.length){state='error';const code=errors[0]?.status;reason=code==='loginExpired'?'登录已失效，新消息暂未更新。':code==='captcha'?'需要处理验证码，新消息暂未更新。':code==='pageChanged'?'平台页面发生变化，抓取暂时中断。':code==='riskControl'?'平台要求检查账号状态，抓取暂时中断。':'抓取服务中断或心跳超时，新消息暂未更新。';}
 else if(rows.length&&lastSuccessAt&&now-timestamp(lastSuccessAt)<=30*60000&&workers.length&&workers.every(a=>a.status==='online'&&now-timestamp(a.lastHeartbeatAt)<=5*60000)){state='healthy';}
 else if(lastSuccessAt&&now-timestamp(lastSuccessAt)>30*60000){state='error';reason='长时间没有收到成功抓取记录，请检查抓取系统。';}
 else reason=rows.length?'等待抓取系统报告健康状态。':'尚未获取平台抓取记录。';
 return {type,name,state,lastSuccessAt,lastCheckAt,reason,key:[state,reason,lastSuccessAt,lastCheckAt].join('|'),channels:rows,agents:workers};
}
