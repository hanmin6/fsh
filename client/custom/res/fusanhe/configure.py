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
x={'tabList':['ExternalConversation','Account','Contact','Lead','Opportunity','Task','Email','KnowledgeDocument','OutboundTask','AIReplyDraft','AutomationAgent'],'language':'zh_CN'}
r=urllib.request.Request('http://localhost:8080/api/v1/Settings',data=json.dumps(x).encode(),headers=h,method='PUT')
with urllib.request.urlopen(r) as f: print('Navigation and Chinese default configured:',f.status)
