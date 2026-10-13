import test from 'node:test';
import assert from 'node:assert/strict';
import {accountState,canPoll,qrRemaining,wechatError,type WeChatAccount} from './wechat-model';
const a:WeChatAccount={id:'account-1',name:'负责人',enabled:true,status:'unbound',boundAt:null,lastInboundAt:null,lastTestAt:null,testStatus:null,error:null,qr:null};
test('binding is distinct from notification availability',()=>{assert.equal(accountState(a),'待绑定');assert.equal(accountState({...a,status:'bound'}),'已绑定');assert.equal(accountState({...a,status:'bound',enabled:false}),'提醒已停用')});
test('expired, blocked and generating QR codes never keep polling',()=>{const now=Date.parse('2026-10-12T00:00:00Z'),qr={version:'one',url:'https://weixin.qq.com/q',expiresAt:'2026-10-12T00:00:05Z',state:'wait' as const};assert.equal(qrRemaining(qr,now),5);assert.equal(canPoll(qr,now),true);assert.equal(qrRemaining(qr,now+6000),0);assert.equal(canPoll(qr,now+5000),false);assert.equal(canPoll({...qr,state:'error'},now),false);assert.equal(canPoll({...qr,state:'generating'},now),false)});
test('uncertain send status asks for checking WeChat before retrying',()=>{assert.match(wechatError('test_uncertain'),/避免重复发送/);assert.match(wechatError('duplicate_wechat'),/另一个微信/);assert.match(wechatError('unknown'),/重试/)});
