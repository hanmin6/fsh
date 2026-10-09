import type {Row} from './domain';
export type ProductImage={id:string;name:string;dataUrl:string;sha256:string;linked:boolean};
export type ProductContext={product:Row;specs:Row[];images:ProductImage[]};
export type CreativePlan={name:string;description:string;motion:string;use:string};
export const videoDirections=[
 {name:'产品展示',description:'以所选产品图为首帧，展示主体与质感，背景干净。',motion:'镜头缓慢推近，主体保持稳定，不改变产品和包装外观。',use:'独立站、客户介绍'},
 {name:'食用场景',description:'围绕产品安排符合实际用途的食用场景；资料不足时采用简洁桌面展示。',motion:'镜头小幅横移，突出主体，不虚构配料、功效或认证。',use:'社交宣传'},
 {name:'包装展示',description:'展示所选图片中实际存在的包装；没有包装图时展示产品细节。',motion:'从整体轻推至细节，不新增包装、标签文字或未经核实的信息。',use:'B2B 产品推广'},
] satisfies CreativePlan[];
export function productBrief(product:Row,specs:Row[],extra:string){
 const facts=[`产品：${product.name||'未命名产品'}`,product.nameEn?`英文名：${product.nameEn}`:'',product.category?`分类：${product.category}`:''];
 // Import descriptions contain private provenance after this marker.
 const description=String(product.description||'').split(/(?:来源|原始来源|SHA-256)[：:]/)[0].trim();
 if(description)facts.push(`产品介绍：${description.slice(0,400)}`);
 for(const spec of specs.filter(s=>s.status==='approved').slice(0,3))for(const [field,label] of [['packingSpec','包装'],['ingredients','配料'],['shelfLife','保质期'],['storageConditions','储存条件'],['customerVisibleNotes','说明']])if(spec[field])facts.push(`${label}：${String(spec[field]).slice(0,180)}`);
 if(extra.trim())facts.push(`补充要求：${extra.trim()}`);
 facts.push('按产品展示、食用场景、包装展示三个方向推荐；仅使用已有事实，不编造功效、认证或包装。');
 let result=facts.join('\n');const encoder=new TextEncoder();
 while(encoder.encode(result).length>1900)result=result.slice(0,-1);
 return result;
}
export function mergeProductImages(images:ProductImage[]){const seen=new Set<string>();return [...images].sort((a,b)=>Number(b.linked)-Number(a.linked)).filter(image=>{const key=image.sha256||image.id;if(seen.has(key))return false;seen.add(key);return true})}
