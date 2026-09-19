#!/usr/bin/env python3
"""Runtime closed-loop verification against a running instance with demo data.

Updated for phase 1 rules:
- Conversations no longer enter 'sent': the send state lives on the task and
  a replied conversation shows 'replied' (legacy 'sent' still accepted for
  pre-phase-1 data).
- Mock sends record deliveryStatus 'mockSent' so simulated receipts are never
  mistaken for real ones; 'sent' remains valid for real sends.
- sendSuccessRate is a rate between 0 and 1 over all tasks (test databases
  legitimately contain cancelled/failed tasks); the assertion requires at
  least one successful send instead of a 100% rate.
"""
import base64,json,os,urllib.request,unittest
BASE=os.getenv('ESPOCRM_API_URL','http://localhost:8080/api/v1').rstrip('/')
HEAD={'Authorization':'Basic '+base64.b64encode(f"{os.environ['ESPOCRM_ADMIN_USERNAME']}:{os.environ['ESPOCRM_ADMIN_PASSWORD']}".encode()).decode()}
def get(path):
 with urllib.request.urlopen(urllib.request.Request(BASE+path,headers=HEAD)) as r:return json.load(r)
class Runtime(unittest.TestCase):
 def test_closed_loop_exists(self):
  conversations=get('/ExternalConversation?maxSize=100')['list']
  self.assertTrue(any(x['status'] in ('sent','replied') for x in conversations),'a conversation must have completed a reply (replied in phase 1, sent in legacy data)')
  messages=get('/ExternalMessage?maxSize=100')['list'];self.assertTrue(any(x['direction']=='inbound' for x in messages))
  self.assertTrue(any(x['direction']=='outbound' and x['deliveryStatus'] in ('sent','mockSent') for x in messages),'an outbound receipt must exist (mockSent for mock sends)')
  tasks=get('/OutboundTask?maxSize=100')['list'];self.assertTrue(any(x['status']=='sent' and x['platformMessageId'] for x in tasks))
 def test_dashboard_and_audit(self):
  d=get('/Fusanhe/dashboard');
  for key in ('todayInquiries','waitingReply','waitingApproval','slaBreached','averageFirstResponseMinutes','aiDrafts','humanEditRate','sendSuccessRate','failedTasks'):self.assertIn(key,d)
  self.assertGreaterEqual(d['sendSuccessRate'],0);self.assertLessEqual(d['sendSuccessRate'],1)
  self.assertGreater(d['sendSuccessRate'],0,'at least one task must have been sent successfully')
  self.assertGreater(get('/AutomationAudit?maxSize=100')['total'],5)
if __name__=='__main__':unittest.main()
