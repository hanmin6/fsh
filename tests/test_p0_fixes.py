import base64
import json
import os
import time
import unittest
import urllib.error
import urllib.request

class TestP0Fixes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base_url = os.environ.get('ESPOCRM_API_URL', 'http://localhost:8080/api/v1').rstrip('/')
        user = os.environ.get('ESPOCRM_ADMIN_USERNAME')
        pwd = os.environ.get('ESPOCRM_ADMIN_PASSWORD')
        if not user or not pwd:
            raise unittest.SkipTest('Set ESPOCRM_ADMIN_USERNAME and ESPOCRM_ADMIN_PASSWORD for runtime tests.')
        cls.auth_header = 'Basic ' + base64.b64encode(f"{user}:{pwd}".encode()).decode()
        cls.headers = {
            'Authorization': cls.auth_header,
            'Content-Type': 'application/json'
        }
        cls.auto_token = os.environ.get('FUSANHE_AUTOMATION_TOKEN')
        if not cls.auto_token:
            raise unittest.SkipTest('Set FUSANHE_AUTOMATION_TOKEN for runtime tests.')
        cls.agent_headers = {
            'X-Automation-Token': cls.auto_token,
            'Content-Type': 'application/json'
        }

    def test_new_customer_intake_receives_without_auto_lead(self):
        """P0 #1 / Phase 1: intake must not error for brand-new customers.

        Updated for the phase 1 product rule: unknown inquiries are received
        with an identity mapping and stay unlinked - intake no longer
        auto-creates a Lead, so createdLead is now asserted to be False.
        """
        unique_id = f"NEW-{int(time.time() * 1000)}"
        payload = {
            'channelType': 'Alibaba',
            'conversationExternalId': f"CONV-{unique_id}",
            'messageExternalId': f"MSG-{unique_id}",
            'senderName': f"Brand New Buyer {unique_id}",
            'company': f"Unique Global Corp {unique_id}",
            'email': f"buyer_{unique_id}@uniqueglobal.com",
            'body': 'Inquiry from brand new customer needing automatic lead creation.',
            'country': 'Germany',
            'language': 'de',
            'product': 'Stainless Steel Flange'
        }

        req = urllib.request.Request(
            f"{self.base_url}/Fusanhe/mock/intake",
            data=json.dumps(payload).encode('utf-8'),
            headers=self.headers
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            self.assertEqual(resp.status, 200)
            res = json.load(resp)
            self.assertFalse(res.get('deduplicated'))
            self.assertFalse(res.get('createdLead'), "Phase 1: intake must not auto-create a Lead")
            self.assertTrue(res.get('identityId'), "An identity mapping must be created")
            self.assertTrue(res.get('conversationId'))
            conv_id = res['conversationId']

        # Verify conversation entity in CRM
        req_conv = urllib.request.Request(
            f"{self.base_url}/ExternalConversation/{conv_id}",
            headers=self.headers
        )
        with urllib.request.urlopen(req_conv, timeout=10) as resp:
            conv = json.load(resp)
            self.assertTrue(conv.get('needsManualMatch'), "Unlinked identity requires manual confirmation")
            self.assertEqual(conv.get('status'), 'pending')

    def test_dashboard_get_is_strictly_read_only(self):
        """P0 #2: GET /Fusanhe/dashboard must be free of side-effects."""
        # Query conversations modifiedAt before dashboard call
        req_list = urllib.request.Request(
            f"{self.base_url}/ExternalConversation?maxSize=50",
            headers=self.headers
        )
        with urllib.request.urlopen(req_list, timeout=10) as resp:
            before_convs = {c['id']: c.get('modifiedAt') for c in json.load(resp).get('list', [])}

        # Call dashboard multiple times
        for _ in range(3):
            req_dash = urllib.request.Request(
                f"{self.base_url}/Fusanhe/dashboard",
                headers=self.headers
            )
            with urllib.request.urlopen(req_dash, timeout=10) as resp:
                self.assertEqual(resp.status, 200)
                dash = json.load(resp)
                self.assertIn('todayInquiries', dash)
                self.assertIn('slaBreached', dash)

        # Query conversations modifiedAt after dashboard calls
        with urllib.request.urlopen(req_list, timeout=10) as resp:
            after_convs = {c['id']: c.get('modifiedAt') for c in json.load(resp).get('list', [])}

        # modifiedAt timestamps must remain identical
        for cid, mod_before in before_convs.items():
            self.assertEqual(mod_before, after_convs.get(cid), f"Conversation {cid} was modified by GET /dashboard")

    def test_claim_validates_agent_registration_and_status(self):
        """P1 #1: Claim must reject unregistered agents."""
        req = urllib.request.Request(
            f"{self.base_url}/Fusanhe/agent/claim",
            data=json.dumps({'agentKey': 'unregistered-ghost-agent'}).encode('utf-8'),
            headers=self.agent_headers
        )
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(req, timeout=10)
        self.assertEqual(ctx.exception.code, 404)

if __name__ == '__main__':
    unittest.main()
