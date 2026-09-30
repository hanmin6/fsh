import {test} from 'node:test';
import assert from 'node:assert/strict';
import {origin,certificateState,sortFollowups} from './domain';
test('production attribution never infers AI from current mode or demo fields',()=>{
 assert.equal(origin({id:'1',direction:'outbound',senderName:'客服',controlMode:'ai',origin:'ai'}),'来源未确认 · 客服');
 assert.equal(origin({id:'2',direction:'inbound',senderName:'王先生'}),'客户 · 王先生');
});
test('certificate requires approval and expiry and respects Shanghai calendar boundary',()=>{
 const now=new Date('2026-09-28T16:01:00Z');
 assert.equal(certificateState({id:'1',status:'approved',validTo:'2026-09-28'},now),'已过期');
 assert.equal(certificateState({id:'1',status:'approved'},now),'有效期待核对');
 assert.equal(certificateState({id:'1',status:'revoked',validTo:'2028-01-01'},now),'已撤销');
 assert.equal(certificateState({id:'1',status:'approved',validTo:'2028-01-01',validFrom:'2027-01-01'},now),'尚未生效');
});
test('followups sort overdue first and missing rating after rated ties',()=>{
 assert.deepEqual(sortFollowups([{id:'none'},{id:'a',rating:'A'},{id:'late',dateEnd:'2026-09-28 00:00:00'},{id:'s',rating:'S'}]).map(r=>r.id),['late','s','a','none']);
});
