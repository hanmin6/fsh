#!/usr/bin/env python3
"""Idempotently install navigation and baseline roles through the EspoCRM API."""
import base64, json, os, urllib.parse, urllib.request
base=os.getenv('ESPOCRM_API_URL','http://localhost:8080/api/v1').rstrip('/')
user=os.environ['ESPOCRM_ADMIN_USERNAME']; password=os.environ['ESPOCRM_ADMIN_PASSWORD']
headers={'Authorization':'Basic '+base64.b64encode(f'{user}:{password}'.encode()).decode(),'Content-Type':'application/json'}
def request(path,method='GET',body=None):
 req=urllib.request.Request(base+path,None if body is None else json.dumps(body).encode(),headers,method=method)
 with urllib.request.urlopen(req) as r:return json.load(r) if r.length != 0 else {}
settings=request('/Settings');tabs=[t for t in settings.get('tabList',[]) if t not in ('MediaAsset','CreativePlan','MediaJob')]
for item in ('ExternalConversation','KnowledgeDocument','OutboundTask'):
 if item not in tabs:tabs.append(item)
# Industry modules stay hidden unless their feature flag is enabled.
flags={
 'FUSANHE_FEATURE_PRODUCTS':('FusanheProduct','FusanheProductSpec'),
 'FUSANHE_FEATURE_CERTIFICATES':('FusanheCertificate',),
 'FUSANHE_FEATURE_SAMPLES':('FusanheSample',),
 'FUSANHE_FEATURE_QUOTES':('FusanheInquiry','FusanheQuote','FusanheQuoteItem'),
 'FUSANHE_FEATURE_ORDERS':('FusanheSalesOrder','FusanheOrderLine','FusanheOrderShipment','FusanheShipmentItem'),
}
for var,names in flags.items():
 if os.getenv(var,'').strip().lower() in ('1','true','yes'):
  for item in names:
   if item not in tabs:tabs.append(item)
request('/Settings','PUT',{'tabList':tabs})
entities=('Account','Contact','Lead','Opportunity','Task','ExternalConversation','ExternalIdentity','ExternalMessage','AIReplyDraft','OutboundTask','KnowledgeDocument',
          'FusanheProduct','FusanheProductSpec','FusanheCertificate','FusanheSample','FusanheInquiry','FusanheQuote','FusanheQuoteItem',
          'FusanheSalesOrder','FusanheOrderLine','FusanheOrderShipment','FusanheShipmentItem',
          'MediaAsset','CreativePlan','MediaJob')
# A partial rollout may not have every industry scope yet.
flag_of={'FusanheProduct':'FUSANHE_FEATURE_PRODUCTS','FusanheProductSpec':'FUSANHE_FEATURE_PRODUCTS',
 'FusanheCertificate':'FUSANHE_FEATURE_CERTIFICATES','FusanheSample':'FUSANHE_FEATURE_SAMPLES',
 'FusanheInquiry':'FUSANHE_FEATURE_QUOTES','FusanheQuote':'FUSANHE_FEATURE_QUOTES','FusanheQuoteItem':'FUSANHE_FEATURE_QUOTES',
 'FusanheSalesOrder':'FUSANHE_FEATURE_ORDERS','FusanheOrderLine':'FUSANHE_FEATURE_ORDERS',
 'FusanheOrderShipment':'FUSANHE_FEATURE_ORDERS','FusanheShipmentItem':'FUSANHE_FEATURE_ORDERS'}
deployed=[]
for entity in entities:
 var=flag_of.get(entity)
 if var and os.getenv(var,'').strip().lower() not in ('1','true','yes'):
  print(f'skip {entity}: feature flag {var} off')
  continue
 try:
  # Private creative records intentionally have no generic CRUD read surface.
  request('/Fusanhe/creative/status' if entity in ('MediaAsset','CreativePlan','MediaJob') else f'/{entity}?maxSize=1')
  deployed.append(entity)
 except Exception:
  print(f'skip {entity}: scope not deployed')
entities=tuple(deployed)
def acl(read='all',edit='no',create='no',delete='no'):
 return {e:{'create':create,'read':read,'edit':edit,'delete':delete,'stream':read} for e in entities}
roles={
 '老板':acl('all','no','no','no'),
 '业务主管':acl('all','all','yes','no'),
 '业务员':acl('own','own','yes','no'),
 '平台执行端':acl('no','no','no','no'),
}
# Creative content is private to the creator; ordinary CRUD is guarded server-side.
for role in ('老板', '业务主管', '业务员'):
 for scope in ('MediaAsset', 'CreativePlan', 'MediaJob'):
  if scope in entities: roles[role][scope]={'create':'yes','read':'own','edit':'own' if scope == 'MediaJob' else 'no','delete':'no','stream':'no'}
# Only supervisors can create OutboundTask; the approval endpoint uses this as its permission gate.
roles['老板']['OutboundTask']['create']='yes'
roles['业务主管']['OutboundTask']['create']='yes'
roles['业务员']['OutboundTask']['create']='no'
# Sales handoff creates native Tasks; identities are confirmed from the conversation workspace.
roles['老板']['Task']['edit']='no'
roles['老板']['ExternalIdentity']['edit']='no'
existing=request('/Role?maxSize=100').get('list',[]);by_name={x['name']:x for x in existing}
for name,data in roles.items():
 if name in by_name:request('/Role/'+by_name[name]['id'],'PATCH',{'data':data})
 else:request('/Role','POST',{'name':name,'data':data,'fieldData':{}})
print(json.dumps({'tabs':tabs[-3:],'roles':list(roles),'outboundPaused':os.getenv('FUSANHE_OUTBOUND_PAUSED','true')},ensure_ascii=False))

# Existing installations need an explicit active schedule; metadata alone is insufficient.
if 'MediaJob' in entities:
 schedules=request('/ScheduledJob?maxSize=200').get('list',[])
 matches=[j for j in schedules if j.get('job')=='FusanheMediaReconcile']
 body={'name':'Fusanhe media task reconciliation','job':'FusanheMediaReconcile','status':'Active','scheduling':'* * * * *'}
 if matches:
  request('/ScheduledJob/'+matches[0]['id'],'PATCH',body)
 else:
  request('/ScheduledJob','POST',body)
