#!/usr/bin/env python3
import base64,json,os,urllib.request,unittest
BASE=os.getenv('ESPOCRM_API_URL','http://localhost:8080/api/v1').rstrip('/')
HEAD={'Authorization':'Basic '+base64.b64encode(f"{os.environ['ESPOCRM_ADMIN_USERNAME']}:{os.environ['ESPOCRM_ADMIN_PASSWORD']}".encode()).decode()}
def get(path):
 with urllib.request.urlopen(urllib.request.Request(BASE+path,headers=HEAD)) as r:return json.load(r)
class Runtime(unittest.TestCase):
 def test_closed_loop_exists(self):
  conversations=get('/ExternalConversation?maxSize=20')['list'];self.assertTrue(any(x['status']=='sent' for x in conversations))
  messages=get('/ExternalMessage?maxSize=100')['list'];self.assertTrue(any(x['direction']=='inbound' for x in messages));self.assertTrue(any(x['direction']=='outbound' and x['deliveryStatus']=='sent' for x in messages))
  tasks=get('/OutboundTask?maxSize=20')['list'];self.assertTrue(any(x['status']=='sent' and x['platformMessageId'] for x in tasks))
 def test_dashboard_and_audit(self):
  d=get('/Fusanhe/dashboard');
  for key in ('todayInquiries','waitingReply','waitingApproval','slaBreached','averageFirstResponseMinutes','aiDrafts','humanEditRate','sendSuccessRate','failedTasks'):self.assertIn(key,d)
  self.assertGreaterEqual(d['sendSuccessRate'],1)
  self.assertGreater(get('/AutomationAudit?maxSize=100')['total'],5)
if __name__=='__main__':unittest.main()
