"""Security regression tests from the overnight independent review.

Every test here is a documented bypass attempt that must fail. Status codes:
403 = generic CRUD may not drive workflow state; 200 with forced defaults =
create-time forgery neutralised.
"""
import base64
import json
import os
import unittest
import urllib.error
import urllib.request
import uuid

BASE = os.getenv('ESPOCRM_API_URL', 'http://localhost:8088/api/v1').rstrip('/')
ADMIN = base64.b64encode(
    f"{os.environ.get('ESPOCRM_ADMIN_USERNAME', 'admin')}:{os.environ.get('ESPOCRM_ADMIN_PASSWORD', '')}".encode()
).decode()


def call(method, path, data=None, auth=None):
    headers = {'Content-Type': 'application/json', 'Authorization': auth or ('Basic ' + ADMIN)}
    req = urllib.request.Request(
        BASE + path,
        json.dumps(data).encode() if data is not None else None,
        headers, method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            body = r.read().decode()
            return r.status, json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        try:
            return e.code, json.loads(body)
        except json.JSONDecodeError:
            return e.code, body


def unique(prefix):
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


class SecurityRegression(unittest.TestCase):
    def test_certificate_status_cannot_be_forged(self):
        """Review finding #1 (P1): PATCH /FusanheCertificate status."""
        s, cert = call('POST', '/FusanheCertificate', {
            'name': f'Forge Test {unique("C")}', 'type': 'halal', 'scopeLevel': 'factory',
        })
        self.assertEqual(s, 200, cert)
        s, err = call('PATCH', f"/FusanheCertificate/{cert['id']}", {'status': 'approved'})
        self.assertEqual(s, 403, err)
        s, ent = call('GET', f"/FusanheCertificate/{cert['id']}")
        self.assertEqual(ent['status'], 'draft')

    def test_approved_spec_cannot_be_unapproved(self):
        """Review finding #2 (P2): approved spec must not flip back to draft."""
        s, prod = call('POST', '/FusanheProduct', {'name': unique('SEC'), 'code': unique('S')})
        s, spec = call('POST', '/FusanheProductSpec', {'name': 'v1', 'productId': prod['id'], 'version': 'v1'})
        s, r = call('POST', f"/Fusanhe/product-spec/{spec['id']}/approve")
        self.assertEqual(s, 200)
        s, err = call('PATCH', f"/FusanheProductSpec/{spec['id']}", {'status': 'draft'})
        self.assertEqual(s, 403, err)
        s, ent = call('GET', f"/FusanheProductSpec/{spec['id']}")
        self.assertEqual(ent['status'], 'approved')

    def test_quote_cannot_be_created_as_accepted(self):
        """Review finding #3 (P2): POST /FusanheQuote with status accepted."""
        s, account = call('POST', '/Account', {'name': unique('Forge Buyer')})
        s, quote = call('POST', '/FusanheQuote', {
            'name': f'Forge Quote {unique("Q")}',
            'accountId': account['id'],
            'currency': 'USD',
            'status': 'accepted',
            'acceptedAt': '2026-09-20',
            'acceptedByRef': 'forged acceptance',
        })
        self.assertEqual(s, 200, quote)
        self.assertEqual(quote['status'], 'draft')
        self.assertIsNone(quote['acceptedAt'])
        self.assertIsNone(quote['acceptedByRef'])

    def test_sample_cannot_be_created_in_terminal_state(self):
        """Review finding #4 (P2): POST /FusanheSample with status closed."""
        s, sample = call('POST', '/FusanheSample', {
            'name': f'Forge Sample {unique("S")}',
            'status': 'closed',
            'feedback': 'forged feedback',
            'trackingNo': 'forged',
        })
        self.assertEqual(s, 200, sample)
        self.assertEqual(sample['status'], 'requested')
        self.assertIsNone(sample['trackingNo'])

    def test_conversation_send_states_not_writable_via_crud(self):
        """Review finding #10 (P3): PATCH /ExternalConversation status sent."""
        s, r = call('POST', '/Fusanhe/mock/intake', {
            'channelType': 'Website',
            'conversationExternalId': unique('SEC-CONV'),
            'messageExternalId': unique('SEC-MSG'),
            'senderName': 'Security Probe',
            'email': f'{unique("sec")}@probe.example',
            'body': 'Probe: generic status forgery.',
        })
        conv = r['conversationId']
        s, err = call('PATCH', f'/ExternalConversation/{conv}', {'status': 'sent'})
        self.assertEqual(s, 403, err)
        s, err = call('PATCH', f'/ExternalConversation/{conv}', {'status': 'closed'})
        self.assertEqual(s, 200, 'Human close must remain possible.')

    def test_dashboard_denied_without_read_scope(self):
        """Review finding #6 (P2): users without conversation read get 403."""
        username = f'sec{uuid.uuid4().hex[:10]}'
        s, user = call('POST', '/User', {
            'userName': username, 'lastName': f'SEC {unique("u")}', 'password': 'Sec-Restricted-1!',
        })
        self.assertEqual(s, 200, user)
        restricted = base64.b64encode(f'{username}:Sec-Restricted-1!'.encode()).decode()
        s, err = call('GET', '/Fusanhe/dashboard', auth='Basic ' + restricted)
        self.assertEqual(s, 403, err)
        s, err = call('GET', '/Fusanhe/status', auth='Basic ' + restricted)
        self.assertEqual(s, 403, err)

    def test_intake_rejects_unknown_channel_type(self):
        s, err = call('POST', '/Fusanhe/mock/intake', {
            'channelType': 'MysteryPlatform',
            'conversationExternalId': unique('SEC-CH'),
            'messageExternalId': unique('SEC-CH-M'),
            'body': 'probe',
        })
        self.assertEqual(s, 400, err)


if __name__ == '__main__':
    unittest.main()
