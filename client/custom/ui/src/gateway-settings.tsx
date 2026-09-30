import {useEffect,useState} from 'react';
import type {DataSource} from './bridge';
import {Button,Notice} from './ui';

export function GatewaySettings({source}:{source:DataSource}){
 const [text,setText]=useState<any>(),[media,setMedia]=useState<any>(),[error,setError]=useState(''),[loading,setLoading]=useState(false);
 const refresh=async()=>{
  if(source.demo)return;
  setLoading(true);setError('');
  const results=await Promise.allSettled([source.get('Fusanhe/text/status'),source.get('Fusanhe/creative/status')]);
  setText(results[0].status==='fulfilled'?results[0].value:undefined);
  setMedia(results[1].status==='fulfilled'?results[1].value.media:undefined);
  if(results.some(r=>r.status==='rejected'))setError('部分通道状态无法读取，请检查访问权限或服务部署。');
  setLoading(false);
 };
 useEffect(()=>{void refresh()},[source]);
 return <section aria-label="AI 通道配置"><h3>AI 通道</h3>{source.demo?<Notice>示例预览不会连接模型或产生费用。真实通道状态请切换到真实数据查看。</Notice>:<>
  {error&&<p role="alert" className="w-error">{error}</p>}
  <p><strong>文本 · APIMonth</strong> {text?(text.models?.some((m:any)=>m.available)?'已配置':'未就绪'):'状态待读取'}</p>
  {text?.models?.map((m:any)=><p className="w-muted" key={m.choice}>{m.label} · {m.available?'可选':'不可用'}{m.choice===text.defaultChoice?' · 默认':''}</p>)}
  <p><strong>图片与视频 · TokenDance</strong> {media?(media.enabled&&media.configured?'已启用':'未启用'):'状态待读取'}</p>
  {media&&<p className="w-muted">图片：{media.capabilities?.image?'可用':'未就绪'} · 视频：{media.capabilities?.video?'可用':'未就绪'}</p>}
  <p className="w-muted">配置状态不代表实时健康检测。费用以中转平台账单为准；生成内容需要人工检查。</p>
  <Button disabled={loading} onClick={refresh}>{loading?'正在读取…':'刷新通道状态'}</Button>
 </>}</section>;
}
