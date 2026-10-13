import {test} from 'node:test';
import assert from 'node:assert/strict';
import {categoryChannels,messageUnreadCounts,readMessageCategory} from './message-categories';

const channels=[{id:'ali',type:'Alibaba'},{id:'mic',type:'MadeInChina'},{id:'zoho',type:'Email'},{id:'wa',type:'WhatsApp'},{id:'other',type:'Other'}];
test('channel categories keep email and social separate from marketplace and unknown channels',()=>{
 assert.deepEqual(categoryChannels(channels,'platform').map(c=>c.id),['ali','mic']);
 assert.deepEqual(categoryChannels(channels,'email').map(c=>c.id),['zoho']);
 assert.deepEqual(categoryChannels(channels,'social').map(c=>c.id),['wa']);
 assert.equal(categoryChannels(channels,'all').length,5);
 assert.equal(readMessageCategory('identity'),'all');
});
test('unread counts include unclassified conversations only in all and do not double count records',()=>{
 const rows=[{id:'a',channelId:'ali',unreadCount:3},{id:'a',channelId:'ali',unreadCount:3},{id:'e',channelId:'zoho',unreadCount:2},{id:'s',channelId:'wa',unreadCount:1},{id:'u',channelId:'other',unreadCount:4},{id:'orphan',channelId:'missing',unreadCount:5},{id:'bad',channelId:'ali',unreadCount:-1}];
 assert.deepEqual(messageUnreadCounts(channels,rows),{all:15,platform:3,email:2,social:1});
});
