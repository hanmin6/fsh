"""WP2: certificates and test reports (feature-flagged module).

Covers review lifecycle, validity rules (draft/expired/revoked never count as
valid), the expiry list, AI-context sourcing and ACL.
"""
import base64
import json
import os
import unittest
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import date, datetime, timedelta, timezone

UTC_DAY = lambda: datetime.now(timezone.utc).date()  # server-side day boundary is UTC

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


class WP2Certificates(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        s, features = call('GET', '/Fusanhe/features')
        if s != 200 or not features.get('features', {}).get('certificates'):
            raise unittest.SkipTest('FUSANHE_FEATURE_CERTIFICATES is not enabled on this stack.')

    def make_cert(self, **overrides):
        payload = {
            'name': f'清真证书 {unique("CERT")}',
            'type': 'halal',
            'scopeLevel': 'factory',
            'factoryName': '山东清真食品加工厂',
            'issuer': '中国伊斯兰教协会演示签发方',
            'certificateNo': unique('HALAL'),
            'issueDate': UTC_DAY().isoformat(),
            'validFrom': UTC_DAY().isoformat(),
            'validTo': (UTC_DAY() + timedelta(days=365)).isoformat(),
            'markets': '中东、东南亚',
        }
        payload.update(overrides)
        s, cert = call('POST', '/FusanheCertificate', payload)
        self.assertEqual(s, 200, cert)
        return cert

    def approve(self, cert_id):
        return call('POST', f'/Fusanhe/certificate/{cert_id}/approve')

    def test_lifecycle_and_validity_rules(self):
        cert = self.make_cert()
        # Draft is not a valid certificate.
        s, exp = call('GET', '/Fusanhe/certificates/expiring?days=365')
        self.assertFalse(any(x['id'] == cert['id'] for x in exp['list']),
                         'Draft certificate must not appear as valid.')
        s, ok = self.approve(cert['id'])
        self.assertEqual(s, 200, ok)
        s, exp = call('GET', '/Fusanhe/certificates/expiring?days=365')
        self.assertTrue(any(x['id'] == cert['id'] and not x['expired'] for x in exp['list']))
        # Double approval is a conflict.
        s, err = self.approve(cert['id'])
        self.assertEqual(s, 409)
        # Revoked certificates are not valid either.
        s, rev = call('POST', f"/Fusanhe/certificate/{cert['id']}/revoke")
        self.assertEqual(s, 200, rev)
        s, rev2 = call('POST', f"/Fusanhe/certificate/{cert['id']}/revoke")
        self.assertEqual(s, 409)
        s, exp = call('GET', '/Fusanhe/certificates/expiring?days=365')
        self.assertFalse(any(x['id'] == cert['id'] for x in exp['list']))

    def test_expired_certificate_flagged_not_hidden(self):
        """Expired approved certs appear in the list flagged expired=true."""
        cert = self.make_cert(validTo=(UTC_DAY() - timedelta(days=1)).isoformat())
        s, _ = self.approve(cert['id'])
        s, exp = call('GET', '/Fusanhe/certificates/expiring?days=30')
        match = [x for x in exp['list'] if x['id'] == cert['id']]
        self.assertTrue(match, 'Expired certificate must surface in the expiry list.')
        self.assertTrue(match[0]['expired'])

    def test_expiring_horizon_param_clamped(self):
        s, exp = call('GET', '/Fusanhe/certificates/expiring?days=99999')
        self.assertEqual(s, 200)
        self.assertEqual(exp['days'], 365)
        s, exp = call('GET', '/Fusanhe/certificates/expiring?days=0')
        self.assertEqual(exp['days'], 1)

    def test_ai_context_uses_only_valid_certificates(self):
        """Only approved+valid certs feed AI context, with source citation."""
        good = self.make_cert(type='halal', scopeLevel='product')
        self.approve(good['id'])
        draft_cert = self.make_cert(type='brc')
        # keep draft_cert unapproved; revoked one must be ignored too
        revoked = self.make_cert(type='iso22000')
        self.approve(revoked['id'])
        call('POST', f"/Fusanhe/certificate/{revoked['id']}/revoke")

        ts = unique('AICTX')
        s, r = call('POST', '/Fusanhe/mock/intake', {
            'channelType': 'Website',
            'conversationExternalId': ts,
            'messageExternalId': ts + '-m1',
            'senderName': 'Cert Buyer',
            'email': f'{ts}@certctx.example',
            'body': 'Do you have halal and BRC certificates for canned products?',
        })
        conv = r['conversationId']
        s, gen = call('POST', f'/Fusanhe/conversation/{conv}/generate-draft')
        self.assertEqual(s, 200, gen)
        cited = gen.get('citedKnowledge') or []
        self.assertIn('cert:' + good['id'], cited,
                      'Valid approved certificate should be cited.')
        self.assertNotIn('cert:' + draft_cert['id'], cited)
        self.assertNotIn('cert:' + revoked['id'], cited)

    def test_restricted_user_cannot_review_certificates(self):
        username = f'wp2{uuid.uuid4().hex[:10]}'
        s, user = call('POST', '/User', {
            'userName': username, 'lastName': f'WP2 {unique("u")}', 'password': 'Wp2-Restricted-1!',
        })
        self.assertEqual(s, 200, user)
        cert = self.make_cert()
        restricted = base64.b64encode(f'{username}:Wp2-Restricted-1!'.encode()).decode()
        s, err = call('POST', f'/Fusanhe/certificate/{cert["id"]}/approve', auth='Basic ' + restricted)
        self.assertEqual(s, 403, err)
        s, err = call('POST', f'/Fusanhe/certificate/{cert["id"]}/revoke', auth='Basic ' + restricted)
        self.assertEqual(s, 403, err)


if __name__ == '__main__':
    unittest.main()
