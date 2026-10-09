import {test} from 'node:test';
import assert from 'node:assert/strict';
import {productBrief,mergeProductImages} from './product-creative';

test('product brief uses public fields and approved specs, never internal provenance',()=>{
 const brief=productBrief({id:'p1',name:'蓝莓',nameEn:'Blueberry',description:'产品简介\n来源：\n/private/share.xlsx',internalNotes:'secret'},[{id:'s1',status:'approved',packingSpec:'10 kg',ingredients:'蓝莓',internalNotes:'secret'},{id:'s2',status:'draft',packingSpec:'unverified'}],'背景干净');
 assert.match(brief,/蓝莓/);assert.match(brief,/10 kg/);assert.match(brief,/背景干净/);
 assert.doesNotMatch(brief,/private|secret|unverified/);
});
test('matching images are candidates; linked image wins and hashes deduplicate originals',()=>{
 const images=mergeProductImages([{id:'a',sha256:'same',name:'linked',dataUrl:'data:a',linked:true},{id:'b',sha256:'same',name:'candidate',dataUrl:'data:b',linked:false},{id:'c',sha256:'other',name:'other',dataUrl:'data:c',linked:false}]);
 assert.deepEqual(images.map(x=>x.id),['a','c']);assert.equal(images[1].linked,false);
});
test('a long Chinese product brief fits the server UTF-8 byte limit',()=>{
 const brief=productBrief({id:'p',name:'产品',description:'资料'.repeat(300)},[{id:'s',status:'approved',packingSpec:'包装'.repeat(120),ingredients:'配料'.repeat(120)}],'要求'.repeat(150));
 assert.ok(new TextEncoder().encode(brief).length<=2000);
});
