import type {Row} from './domain';

export type MessageCategory='all'|'platform'|'email'|'social';
export const messageCategories:{id:MessageCategory;label:string}[]=[{id:'all',label:'全部消息'},{id:'platform',label:'平台消息'},{id:'email',label:'邮件消息'},{id:'social',label:'社交消息'}];
const platformTypes=new Set(['Alibaba','MadeInChina']);
const socialTypes=new Set(['WhatsApp','Facebook','Instagram','LinkedIn','Twitter','X','WeChat']);
export const channelLabels:Record<string,string>={Alibaba:'阿里国际站',MadeInChina:'中国制造网',Email:'邮件',WhatsApp:'WhatsApp',Website:'官网',Other:'其他',Facebook:'Facebook',Instagram:'Instagram',LinkedIn:'LinkedIn',Twitter:'X',X:'X',WeChat:'微信'};
export function channelCategory(type?:string):MessageCategory|null{return platformTypes.has(type||'')?'platform':type==='Email'?'email':socialTypes.has(type||'')?'social':null}
export function readMessageCategory(tab:string):MessageCategory{return messageCategories.some(c=>c.id===tab)?tab as MessageCategory:'all'}
export function categoryChannels(channels:Row[],category:MessageCategory){return category==='all'?channels:channels.filter(c=>channelCategory(c.type)===category)}
export function messageUnreadCounts(channels:Row[],conversations:Row[]):Record<MessageCategory,number>{
 const counts={all:0,platform:0,email:0,social:0};const types=new Map(channels.map(c=>[c.id,channelCategory(c.type)]));const seen=new Set<string>();
 for(const r of conversations){if(seen.has(r.id))continue;seen.add(r.id);const n=Number(r.unreadCount);if(!Number.isSafeInteger(n)||n<0)continue;counts.all+=n;const category=types.get(r.channelId);if(category)counts[category]+=n;}
 return counts;
}
