#!/usr/bin/env python3
"""Idempotently install navigation and baseline roles through the EspoCRM API."""
import base64, json, os, urllib.parse, urllib.request
base=os.getenv('ESPOCRM_API_URL','http://localhost:8080/api/v1').rstrip('/')
user=os.environ['ESPOCRM_ADMIN_USERNAME']; password=os.environ['ESPOCRM_ADMIN_PASSWORD']
headers={'Authorization':'Basic '+base64.b64encode(f'{user}:{password}'.encode()).decode(),'Content-Type':'application/json'}
def request(path,method='GET',body=None):
 req=urllib.request.Request(base+path,None if body is None else json.dumps(body).encode(),headers,method=method)
 with urllib.request.urlopen(req) as r:return json.load(r) if r.length != 0 else {}
settings=request('/Settings');tabs=settings.get('tabList',[])
for item in ('ExternalConversation','KnowledgeDocument','OutboundTask'):
 if item not in tabs:tabs.append(item)
request('/Settings','PUT',{'tabList':tabs})
entities=('Account','Contact','Lead','Opportunity','ExternalConversation','ExternalMessage','AIReplyDraft','OutboundTask','KnowledgeDocument')
def acl(read='all',edit='no',create='no',delete='no'):
 return {e:{'create':create,'read':read,'edit':edit,'delete':delete,'stream':read} for e in entities}
roles={
 '老板':acl('all','no','no','no'),
 '业务主管':acl('all','all','yes','no'),
 '业务员':acl('own','own','yes','no'),
 '平台执行端':acl('no','no','no','no'),
}
# Only supervisors can create OutboundTask; the approval endpoint uses this as its permission gate.
roles['老板']['OutboundTask']['create']='yes'
roles['业务主管']['OutboundTask']['create']='yes'
roles['业务员']['OutboundTask']['create']='no'
existing=request('/Role?maxSize=100').get('list',[]);by_name={x['name']:x for x in existing}
for name,data in roles.items():
 if name in by_name:request('/Role/'+by_name[name]['id'],'PATCH',{'data':data})
 else:request('/Role','POST',{'name':name,'data':data,'fieldData':{}})
print(json.dumps({'tabs':tabs[-3:],'roles':list(roles),'outboundPaused':os.getenv('FUSANHE_OUTBOUND_PAUSED','true')},ensure_ascii=False))
