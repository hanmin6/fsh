import test from 'node:test';import assert from 'node:assert/strict';import {assessCapture} from './capture-model';
const now=Date.parse('2026-09-30T02:00:00Z');const channels=[{id:'c',type:'Alibaba',lastSyncAt:'2026-09-30 01:59:00'}];const agent={id:'a',mode:'real',capabilities:['Alibaba'],status:'online',lastHeartbeatAt:'2026-09-30 01:59:50'};
test('normal requires a real successful observation and recent worker',()=>assert.equal(assessCapture('Alibaba',channels,[agent],now).state,'healthy'));
test('bridge or empty status never fabricate success',()=>assert.equal(assessCapture('Alibaba',[],[],now).state,'checking'));
test('login failures retain last successful capture',()=>{const s=assessCapture('Alibaba',channels,[{...agent,status:'loginExpired'}],now);assert.equal(s.state,'error');assert.equal(s.lastSuccessAt,channels[0].lastSyncAt);assert.match(s.reason,/登录/)});
test('stale workers fail independently per platform',()=>{assert.equal(assessCapture('Alibaba',channels,[{...agent,lastHeartbeatAt:'2026-09-30 01:00:00'}],now).state,'error');assert.equal(assessCapture('MadeInChina',channels,[agent],now).state,'checking')});
test('newer failed attempts never replace successful time',()=>assert.equal(assessCapture('Alibaba',channels,[{...agent,status:'captcha'}],now).lastSuccessAt,channels[0].lastSyncAt));

test('missing heartbeat cannot confirm a healthy worker',()=>assert.equal(assessCapture('Alibaba',channels,[{...agent,lastHeartbeatAt:null}],now).state,'error'));
test('invalid capture timestamp is not a successful observation',()=>assert.equal(assessCapture('Alibaba',[{...channels[0],lastSyncAt:'invalid'}],[agent],now).state,'checking'));

test('heartbeat alone cannot hide stale successful captures',()=>assert.equal(assessCapture('Alibaba',[{...channels[0],lastSyncAt:'2026-09-29 01:00:00'}],[agent],now).state,'error'));
