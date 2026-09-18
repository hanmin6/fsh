import os
import unittest
import urllib.request
import json
import base64

class TestAlibabaConnector(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.environ.get('RUN_ALIBABA_INTEGRATION_TESTS') != '1':
            raise unittest.SkipTest('Set RUN_ALIBABA_INTEGRATION_TESTS=1 to call the remote bridge.')
        cls.base_url = os.environ.get('ESPOCRM_API_URL', 'http://localhost:8080/api/v1').rstrip('/')
        user = os.environ.get('ESPOCRM_ADMIN_USERNAME')
        pwd = os.environ.get('ESPOCRM_ADMIN_PASSWORD')
        cls.bridge_token = os.environ.get('ALIBABA_BRIDGE_TOKEN')
        if not user or not pwd or not cls.bridge_token:
            raise unittest.SkipTest('CRM credentials and ALIBABA_BRIDGE_TOKEN are required.')
        cls.auth_header = 'Basic ' + base64.b64encode(f"{user}:{pwd}".encode()).decode()
        cls.headers = {
            'Authorization': cls.auth_header,
            'Content-Type': 'application/json'
        }

    def test_remote_bridge_direct_status(self):
        """Verify the remote alibaba-api bridge (api.fsh.digital) returns healthy status."""
        bridge_url = os.environ.get('ALIBABA_BRIDGE_URL', 'https://api.fsh.digital').rstrip('/')
        bridge_token = self.bridge_token

        req = urllib.request.Request(
            f"{bridge_url}/alibaba/channel/status",
            headers={
                'Authorization': f"Bearer {bridge_token}",
                'Accept': 'application/json'
            }
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            self.assertEqual(resp.status, 200)
            data = json.load(resp)
            self.assertTrue(data.get('ok'))
            self.assertEqual(data.get('channel'), 'Alibaba')
            self.assertTrue(data.get('connected'))
            self.assertEqual(data.get('status'), 'healthy')
            self.assertFalse(data.get('isExpired'))
            self.assertTrue(data.get('account'))
            self.assertTrue(data.get('sellerId'))

    def test_crm_status_endpoint_reports_alibaba_healthy(self):
        """Verify CRM /Fusanhe/status integrates AlibabaConnector and reports channel health."""
        req = urllib.request.Request(
            f"{self.base_url}/Fusanhe/status",
            headers=self.headers
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            self.assertEqual(resp.status, 200)
            data = json.load(resp)
            self.assertTrue(data.get('outboundPaused'), "Global outbound pause must remain true")
            channels = data.get('channels', {})
            self.assertIn('Alibaba', channels)
            ali = channels['Alibaba']
            self.assertEqual(ali.get('status'), 'healthy')
            self.assertTrue(ali.get('account'))
            self.assertTrue(ali.get('sellerId'))
            self.assertTrue(ali.get('connected'))

    def test_remote_bridge_webhook_endpoint(self):
        """Verify the remote alibaba-api bridge webhook receives and logs events."""
        if os.environ.get('RUN_ALIBABA_WEBHOOK_TEST') != '1':
            self.skipTest('Set RUN_ALIBABA_WEBHOOK_TEST=1 to write a remote test event.')
        bridge_url = os.environ.get('ALIBABA_BRIDGE_URL', 'https://api.fsh.digital').rstrip('/')
        payload = {
            'event': 'inquiry.new',
            'inquiryId': 'ALI-TEST-999',
            'buyerName': 'Automated Test Buyer',
            'body': 'Inquiry payload test'
        }
        req = urllib.request.Request(
            f"{bridge_url}/alibaba/webhook",
            data=json.dumps(payload).encode('utf-8'),
            headers={'Content-Type': 'application/json'}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            self.assertEqual(resp.status, 200)
            data = json.load(resp)
            self.assertTrue(data.get('ok'))
            self.assertEqual(data.get('status'), 'received')

if __name__ == '__main__':
    unittest.main()
