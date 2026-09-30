import type {Row,Where} from './domain';
export interface HostBridge {
 get(path:string,params?:Record<string,unknown>):Promise<any>;
 post(path:string,data:Record<string,unknown>):Promise<any>;
 patch(path:string,data:Record<string,unknown>):Promise<any>;
 can(entity:string,action?:string):boolean;
 native(entity:string,id?:string,action?:string):void;
 user:{id:string;name:string};
}
export type Result={list:Row[];total:number};
export interface DataSource extends HostBridge {demo:boolean; list(entity:string,options?:{search?:string;where?:Where[];offset?:number;orderBy?:string;order?:string;limit?:number}):Promise<Result>}
export class DataError extends Error {}
export function liveSource(host:HostBridge):DataSource{return {...host,demo:false,async list(entity,options={}){
 if(!host.can(entity,'read'))throw new DataError('没有读取权限，请联系维护人员。');
 try {return await host.get(entity,{maxSize:options.limit||30,offset:options.offset||0,orderBy:options.orderBy||'createdAt',order:options.order||'desc',...(options.search?{textFilter:options.search}:{}),where:options.where||[]});}
 catch(e:any){throw new DataError(e.status===403?'此模块没有访问权限或尚未启用。':e.status===404?'此模块尚未部署。':'数据加载失败，请重试。');}
}}}
