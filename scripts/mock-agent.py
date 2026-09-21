#!/usr/bin/env python3
"""One-shot simulator for the Guangzhou Windows sender. Uses stdlib only."""
import json, os, sys, urllib.request
base=os.getenv('ESPOCRM_API_URL','http://localhost:8080/api/v1').rstrip('/')
bootstrap_token=os.getenv('FUSANHE_AUTOMATION_TOKEN','')
agent=os.getenv('FUSANHE_AGENT_KEY','guangzhou-demo-agent')
capabilities=[c for c in os.getenv('FUSANHE_AGENT_CAPABILITIES','Alibaba,MadeInChina,Website,Email,WhatsApp,Other').split(',') if c]
headers={'Content-Type':'application/json','X-Automation-Token':bootstrap_token}
def post(path,data):
 req=urllib.request.Request(base+path,json.dumps(data).encode(),headers,method='POST')
 with urllib.request.urlopen(req) as r:return json.load(r)
registration=post('/Fusanhe/agent/register',{'agentKey':agent,'name':'广州模拟执行端','mode':'mock','capabilities':capabilities})
credential=registration.get('credential')
if not credential:
 print('Agent registration did not return a credential.',file=sys.stderr);sys.exit(3)
headers['X-Automation-Token']=credential
claimed=post('/Fusanhe/agent/claim',{'agentKey':agent})
if claimed.get('paused'):
 print('Outbound is globally paused.');sys.exit(2)
task=claimed.get('task')
if not task:
 print('No pending task.');sys.exit(0)
post(f"/Fusanhe/agent/task/{task['id']}/sending",{'agentKey':agent})
result=post(f"/Fusanhe/agent/task/{task['id']}/result",{'agentKey':agent,'success':True,'platformMessageId':'MOCK-'+task['id']})
print(json.dumps({'claimed':task['id'],'result':result},ensure_ascii=False))
