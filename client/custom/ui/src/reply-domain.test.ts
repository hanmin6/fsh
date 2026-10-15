import {test} from 'node:test';
import assert from 'node:assert/strict';
import {validateFiles,canGenerate,generationPayload,replyError,sampleAnalysis} from './reply-domain';
const file=(size=100,type='image/png')=>({size,type});
test('image count, MIME, individual and total size enforced before reading',()=>{
 assert.equal(validateFiles([], [file()]),'');
 assert.ok(validateFiles([{size:100},{size:100},{size:100}],[file()]));
 assert.ok(validateFiles([], [file(100,'image/svg+xml')]));
 assert.ok(validateFiles([], [file(0)]));
 assert.ok(validateFiles([], [file(4*1024*1024+1)]));
 assert.ok(validateFiles([{size:4*1024*1024}], [file(4*1024*1024),file()]));
});
test('direction and custom-only are both supported but empty or oversized inputs are not',()=>{
 const direction=sampleAnalysis.directions[0];
 assert.equal(canGenerate('hello',direction,''),true);
 assert.equal(canGenerate('hello',undefined,'先问数量'),true);
 assert.equal(canGenerate('hello',undefined,'   '),false);
 assert.equal(canGenerate('',direction,'reply'),false);
 assert.equal(canGenerate('a'.repeat(12001),direction,''),false);
 assert.equal(canGenerate('hello',direction,'a'.repeat(1501)),false);
});
test('generation and refinement forward current intent and edited draft without screenshots',()=>{
 const p=generationPayload('corrected text',sampleAnalysis.directions[0],'先别降价','en','user edits','shorter');
 assert.equal(p.currentDraft,'user edits');assert.equal(p.text,'corrected text');
 assert.equal(p.refinement,'shorter');assert.equal(p.customInstruction,'先别降价');
 assert.equal('images' in p,false);
 assert.equal(generationPayload('hi',undefined,'custom','auto').direction,null);
});
test('permission and configuration failures are distinguishable without exposing upstream messages',()=>{
 assert.match(replyError({status:403,message:'secret'}),/权限/);
 assert.match(replyError({status:503}),/配置/);
 assert.match(replyError({status:413}),/大小/);
 assert.equal(replyError({message:'secret'}).includes('secret'),false);
});
