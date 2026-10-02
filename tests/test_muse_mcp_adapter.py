import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import urllib.error

ROOT = Path(__file__).resolve().parents[1]
FILE = ROOT / 'integrations/muse_crm_mcp.py'
spec = importlib.util.spec_from_file_location('muse_crm_mcp', FILE)
mcp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mcp)


class AdapterTests(unittest.TestCase):
    def config(self, url='https://gzfusanhesp.com/api/v1'):
        return {'CRM_API_URL': url, 'FUSANHE_AGENT_KEY': 'synthetic-agent',
                'FUSANHE_AGENT_TOKEN': 'synthetic-secret'}

    def test_stdio_handshake_lists_only_narrow_tools(self):
        with tempfile.TemporaryDirectory() as folder:
            config = Path(folder) / 'config.json'
            config.write_text(json.dumps(self.config()))
            lines = [{'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {'protocolVersion': '2025-03-26'}},
                     {'jsonrpc': '2.0', 'method': 'notifications/initialized'},
                     {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list'},
                     {'jsonrpc': '2.0', 'id': 3, 'method': 'tools/call', 'params': {'name': 'send_email'}}]
            result = subprocess.run(['python3', str(FILE), '--config', str(config)],
                                    input='\n'.join(json.dumps(x) for x in lines),
                                    text=True, capture_output=True, check=True)
            responses = [json.loads(x) for x in result.stdout.splitlines()]
            self.assertEqual(len(responses), 3)
            self.assertEqual(responses[0]['result']['protocolVersion'], '2025-03-26')
            self.assertEqual({t['name'] for t in responses[1]['result']['tools']}, set(mcp.ROUTES))
            self.assertTrue(responses[2]['result']['isError'])
            self.assertNotIn('synthetic-secret', result.stdout + result.stderr)

    def test_remote_plaintext_and_embedded_credentials_rejected(self):
        for url in ['http://example.com/api/v1', 'https://user:pass@example.com/api/v1',
                    'https://example.com/api/v1?token=bad']:
            with self.assertRaises(ValueError):
                mcp.Gateway(self.config(url))

    def test_payload_limits_and_unknown_fields_prevent_network(self):
        gateway = mcp.Gateway(self.config())
        with patch.object(gateway.http, 'open') as request:
            for tool, arguments in [('crm_search_prospects', {}),
                                    ('crm_search_prospects', {'name': 'Acme', 'limit': True}),
                                    ('crm_upsert_prospect', {'sourceId': '1', 'company': 'Acme', 'password': 'x'}),
                                    ('crm_record_activity', {'sourceId': '1', 'messageExternalId': 'm', 'body': 'x' * 20001})]:
                self.assertTrue(mcp.dispatch({'method': 'tools/call', 'params': {'name': tool, 'arguments': arguments}}, gateway)['isError'])
            request.assert_not_called()

    def test_ambiguous_post_failure_is_not_retried_and_hides_provider_body(self):
        gateway = mcp.Gateway(self.config())
        error = urllib.error.HTTPError('https://example.com', 503, 'synthetic-secret', {}, None)
        with patch.object(gateway.http, 'open', side_effect=error) as request:
            result = mcp.dispatch({'method': 'tools/call', 'params': {'name': 'crm_upsert_prospect',
                                   'arguments': {'sourceId': 'synthetic-1', 'company': 'Synthetic company'}}}, gateway)
            self.assertEqual(request.call_count, 1)
            self.assertTrue(result['isError'])
            self.assertNotIn('synthetic-secret', json.dumps(result))

    def test_redirect_cannot_forward_agent_headers(self):
        self.assertIsNone(mcp.NoRedirect().redirect_request(None, None, 302, '', {}, 'https://other.example'))


if __name__ == '__main__':
    unittest.main()
