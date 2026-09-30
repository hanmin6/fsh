#!/usr/bin/env python3
"""Apply presentation settings only; run from a trusted local checkout."""
import pathlib,base64,json,urllib.request,subprocess
v={}
for l in (pathlib.Path(__file__).resolve().parents[4] / '.env').read_text().splitlines():
 if '=' in l and not l.startswith('#'):
  k,s=l.split('=',1);v[k]=s.strip().strip('\"\'')
assert v.get('FUSANHE_OUTBOUND_PAUSED','true')=='true', 'Frontend phase requires outbound pause in .env'
result=subprocess.run(['docker','compose','exec','-T','espocrm','php','-r','echo filter_var(getenv("FUSANHE_OUTBOUND_PAUSED") ?: "true", FILTER_VALIDATE_BOOLEAN) ? "paused" : "active";'],cwd=pathlib.Path(__file__).resolve().parents[4],capture_output=True,text=True,check=True)
assert result.stdout.strip()=='paused', 'Running container is not paused. Recreate espocrm from the current .env before configuring.'
h={'Authorization':'Basic '+base64.b64encode((v['ESPOCRM_ADMIN_USERNAME']+':'+v['ESPOCRM_ADMIN_PASSWORD']).encode()).decode(),'Content-Type':'application/json'}
# Native sidebar dividers keep frequent destinations visible and ACL-filtered.
# Preserve installed optional scopes and unrelated user navigation entries.
with urllib.request.urlopen(urllib.request.Request('http://localhost:8080/api/v1/Settings', headers=h)) as f:
 settings=json.load(f)
def flatten(items):
 for item in items:
  if isinstance(item,dict) and 'itemList' in item:
   yield from flatten(item['itemList'])
  else:
   yield item
existing=list(flatten(settings.get('tabList',[])))
scopes={item for item in existing if isinstance(item,str)}
def divider(text): return {'type':'divider','text':text}
def route(text,url,scope): return {'type':'url','text':text,'url':url,'aclScope':scope}
groups=[
 ('客户与销售',['Account','Contact','Lead','Opportunity','Task','Email']),
 ('订单与履约',[name for name in ('FusanheInquiry','FusanheQuote','FusanheQuoteItem','FusanheSample','FusanheSalesOrder','FusanheOrderLine','FusanheOrderShipment','FusanheShipmentItem') if name in scopes]),
 ('客服与审核',['ExternalConversation','AIReplyDraft','ExternalIdentity','OutboundTask']),
 ('产品与资料',['KnowledgeDocument']+[name for name in ('FusanheProduct','FusanheProductSpec','FusanheCertificate') if name in scopes]),
 ('运营管理',['AutomationAgent']),
]
tabs=[divider('工作台'),route('CRM 工作台','#Home/crm','Account'),route('AI 客服工作台','#Home/service','ExternalConversation'),route('历史客户与今日建议','#Home/insights','ExternalConversation')]
for title,items in groups:
 if items: tabs.extend([divider(title),*items])
known={'Home'} | {item for item in tabs if isinstance(item,str)}
urls={item.get('url') for item in tabs if isinstance(item,dict)}
remaining=[item for item in existing if
 (isinstance(item,str) and item not in known and not item.startswith('_delimiter')) or
 (isinstance(item,dict) and item.get('type')=='url' and item.get('url') not in urls)]
if remaining: tabs.extend([divider('其他功能'),*remaining])
x={'tabList':tabs,'language':'zh_CN'}
r=urllib.request.Request('http://localhost:8080/api/v1/Settings',data=json.dumps(x).encode(),headers=h,method='PUT')
with urllib.request.urlopen(r) as f: print('Navigation and Chinese default configured:',f.status)
