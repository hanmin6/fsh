"""WP3: sample management (feature-flagged module).

Covers the request->prepare->send->deliver->feedback->close state machine,
cancel-before-send rule, exception/return records, unique numbers,
follow-up task creation and ACL.
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


class WP3Samples(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        s, features = call('GET', '/Fusanhe/features')
        if s != 200 or not features.get('features', {}).get('samples'):
            raise unittest.SkipTest('FUSANHE_FEATURE_SAMPLES is not enabled on this stack.')

    def make_sample(self, **overrides):
        payload = {
            'name': f'样品单 {unique("SMP")}',
            'quantity': 2,
            'unit': 'carton',
            'feeAmount': 85,
            'feeCurrency': 'USD',
            'recipientName': 'Demo Receiver',
            'recipientAddress': 'Demo Building 1, Dubai',
        }
        payload.update(overrides)
        s, sample = call('POST', '/FusanheSample', payload)
        self.assertEqual(s, 200, sample)
        self.assertTrue(sample['number'], 'Sample number must be generated.')
        return sample

    def act(self, sample_id, action, data=None):
        return call('POST', f'/Fusanhe/sample/{sample_id}/{action}', data or {})

    def test_full_lifecycle(self):
        sample = self.make_sample()
        sid = sample['id']
        # Illegal jump: cannot deliver before sending.
        s, err = self.act(sid, 'deliver')
        self.assertEqual(s, 409, err)
        s, r = self.act(sid, 'prepare')
        self.assertEqual(r['status'], 'preparing')
        s, err = self.act(sid, 'send')
        self.assertEqual(s, 400, 'Send without tracking number must fail.')
        s, r = self.act(sid, 'send', {'trackingNo': 'DEMO-TRACK-001', 'carrier': 'DHL'})
        self.assertEqual(r['status'], 'sent')
        s, r = self.act(sid, 'deliver')
        self.assertEqual(r['status'], 'delivered')
        s, err = self.act(sid, 'feedback')
        self.assertEqual(s, 400, 'Feedback without text must fail.')
        s, r = self.act(sid, 'feedback', {'feedback': '客户认可色泽与口感，要求报整柜价。', 'feedbackResult': 'positive'})
        self.assertEqual(r['status'], 'feedbackReceived')
        s, r = self.act(sid, 'close')
        self.assertEqual(r['status'], 'closed')
        # Closed samples accept nothing further.
        s, err = self.act(sid, 'exception', {'note': 'x'})
        self.assertEqual(s, 409)

    def test_cancel_only_before_sending(self):
        sample = self.make_sample()
        s, r = self.act(sample['id'], 'cancel', {'reason': '客户改为本地采购'})
        self.assertEqual(r['status'], 'cancelled')
        s, err = self.act(sample['id'], 'prepare')
        self.assertEqual(s, 409, 'Cancelled samples must be terminal.')

        sample2 = self.make_sample()
        self.act(sample2['id'], 'prepare')
        self.act(sample2['id'], 'send', {'trackingNo': 'DEMO-TRACK-002'})
        s, err = self.act(sample2['id'], 'cancel', {'reason': 'late cancel'})
        self.assertEqual(s, 409, 'Sent samples cannot be cancelled.')

    def test_return_and_exception_records(self):
        sample = self.make_sample()
        s, err = self.act(sample['id'], 'return', {'note': 'too early'})
        self.assertEqual(s, 409, 'Return before sending must be rejected.')
        s, err = self.act(sample['id'], 'exception', {'note': '清关延误'})
        self.assertEqual(s, 200)
        self.act(sample['id'], 'prepare')
        self.act(sample['id'], 'send', {'trackingNo': 'DEMO-TRACK-003'})
        s, r = self.act(sample['id'], 'return', {'note': '客户拒收：包装破损'})
        self.assertEqual(s, 200)
        s, ent = call('GET', f"/FusanheSample/{sample['id']}")
        self.assertTrue(ent['returned'])
        self.assertIsNotNone(ent['returnedAt'])
        self.assertIn('包装破损', ent['returnNote'])
        self.assertEqual(ent['status'], 'sent', 'Return record must not overwrite the status machine.')
        # Generic PATCH cannot forge workflow fields.
        s, err = call('PATCH', f"/FusanheSample/{sample['id']}", {'status': 'closed'})
        self.assertEqual(s, 403, err)
        s, err = call('PATCH', f"/FusanheSample/{sample['id']}", {'returned': False})
        self.assertEqual(s, 403, err)

    def test_unique_sample_numbers(self):
        sample = self.make_sample()
        s, err = call('POST', '/FusanheSample', {'name': 'dup number test', 'number': sample['number']})
        self.assertEqual(s, 409, err)
        s, err = call('PATCH', f"/FusanheSample/{sample['id']}", {'number': 'CHANGED'})
        self.assertEqual(s, 403, err)

    def test_follow_up_task_from_feedback(self):
        sample = self.make_sample()
        self.act(sample['id'], 'prepare')
        self.act(sample['id'], 'send', {'trackingNo': 'DEMO-TRACK-004'})
        self.act(sample['id'], 'deliver')
        self.act(sample['id'], 'feedback', {'feedback': '客户要求正式报价 1 个整柜。', 'feedbackResult': 'positive'})
        s, first = call('POST', f"/Fusanhe/sample/{sample['id']}/follow-up",
                        {'intent': '报价请求', 'note': '客户要 40HQ 报价'})
        self.assertEqual(s, 200, first)
        self.assertFalse(first['deduplicated'])
        s, second = call('POST', f"/Fusanhe/sample/{sample['id']}/follow-up",
                         {'intent': '报价请求', 'note': '客户要 40HQ 报价'})
        self.assertTrue(second['deduplicated'])
        self.assertEqual(first['taskId'], second['taskId'])
        s, task = call('GET', f"/Task/{first['taskId']}")
        self.assertEqual(task['parentType'], 'FusanheSample')
        self.assertEqual(task['parentId'], sample['id'])

    def test_restricted_user_cannot_transition(self):
        username = f'wp3{uuid.uuid4().hex[:10]}'
        s, user = call('POST', '/User', {
            'userName': username, 'lastName': f'WP3 {unique("u")}', 'password': 'Wp3-Restricted-1!',
        })
        self.assertEqual(s, 200, user)
        sample = self.make_sample()
        restricted = base64.b64encode(f'{username}:Wp3-Restricted-1!'.encode()).decode()
        s, err = self.act(sample['id'], 'prepare')
        s, err = call('POST', f"/Fusanhe/sample/{sample['id']}/prepare", auth='Basic ' + restricted)
        self.assertEqual(s, 403, err)
        s, err = call('POST', f"/Fusanhe/sample/{sample['id']}/follow-up", {'intent': 'x'},
                      auth='Basic ' + restricted)
        self.assertEqual(s, 403, err)


if __name__ == '__main__':
    unittest.main()
