export type ReplyImage = {id:string; name:string; dataUrl:string; size:number};
export type Direction = {id:string; title:string; description:string};
export type Analysis = {recognizedText:string; summaryZh:string; language:string; directions:Direction[]; warnings:string[]};
export type ReplyResult = {draftText:string; translationZh:string; missingInformation:string[]; conflictNote:string};
export type Refinement = ''|'shorter'|'natural'|'formal';
export const languages = [{id:'auto',name:'跟随客户语言'},{id:'en',name:'英语'},{id:'zh',name:'中文'},{id:'es',name:'西班牙语'},{id:'fr',name:'法语'},{id:'de',name:'德语'},{id:'ar',name:'阿拉伯语'},{id:'pt',name:'葡萄牙语'},{id:'ru',name:'俄语'}];
export function validateFiles(existing:Pick<ReplyImage,'size'>[], files:Pick<File,'size'|'type'>[]):string {
 if(existing.length+files.length>3)return '最多上传 3 张截图，请先移除不需要的图片。';
 if(files.some(f=>!['image/png','image/jpeg','image/webp'].includes(f.type)))return '请上传 PNG、JPG 或 WebP 格式的截图。';
 if(files.some(f=>!f.size||f.size>4*1024*1024))return '每张截图需大于 0 且不超过 4 MB，请裁剪或压缩后再上传。';
 if([...existing,...files].reduce((n,f)=>n+f.size,0)>8*1024*1024)return '截图总大小不能超过 8 MB，请移除或压缩部分图片。';
 return '';
}
export function canGenerate(text:string, direction:Direction|undefined, custom:string):boolean {
 return !!text.trim() && text.length<=12000 && custom.length<=1500 && (!!direction||!!custom.trim());
}
export function generationPayload(text:string,direction:Direction|undefined,customInstruction:string,language:string,currentDraft='',refinement:Refinement='') {
 return {operation:'generate',text,direction:direction?{title:direction.title,description:direction.description}:null,customInstruction,language,currentDraft,refinement};
}
export function replyError(error:unknown):string {
 const e=error as {status?:number;responseJSON?:{error?:string};};
 switch(e?.status){
  case 400: return '输入不符合要求，请检查图片格式、大小和文字长度后重试。';
  case 401: return '登录已过期，请重新登录后再试。';
  case 403: return '当前账号没有 AI 草稿创建权限，请联系管理员。';
  case 413: return '截图超过服务器允许的大小，请减少图片或压缩后重试。';
  case 503: return '尚未配置 AI 服务，请联系管理员配置支持图片识别的模型。';
  case 502: return 'AI 服务未返回有效结果，请重试；持续失败时请检查模型的图片识别能力。';
  default: return '处理失败或连接超时，输入已保留，请稍后重试。';
 }
}
// Explicitly synthetic preview, never used by the production API.
export const sampleAnalysis:Analysis={recognizedText:'Customer: Your price is higher than another supplier. Could you offer a better price for freeze-dried strawberries?',summaryZh:'客户认为冻干草莓报价偏高，正在比较其他供应商，希望争取更好的价格。',language:'en',directions:[{id:'direction-1',title:'先了解采购条件',description:'询问数量、包装和目的港，明确比较口径后再评估。'},{id:'direction-2',title:'核对报价差异',description:'了解对方报价的规格和贸易条款，避免只比较单价。'},{id:'direction-3',title:'探讨替代方案',description:'了解预算及用途，再讨论是否有合适的规格或包装。'}],warnings:[]};
export const sampleReply:ReplyResult={draftText:'Thank you for your feedback. Could you share your expected order quantity, packaging requirements and destination port? This will help us review your requirements and prepare a suitable proposal.',translationZh:'感谢您的反馈。方便告知预计采购量、包装要求和目的港吗？这些信息将帮助我们评估您的需求，并准备合适的方案。',missingInformation:['采购数量、包装要求和目的港尚待确认。'],conflictNote:''};
