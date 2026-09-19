"""WP1: product and food spec version tests (feature-flagged module).

Covers review lifecycle, immutability of approved versions, version
traceability, uniqueness, enum/number validation and ACL.
"""
import base64
import json
import os
import unittest
import urllib.error
import urllib.parse
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


class WP1Products(unittest.TestCase):
    def setUp(self):
        s, features = call('GET', '/Fusanhe/features')
        self.assertEqual(s, 200)
        if not features.get('features', {}).get('products'):
            raise unittest.SkipTest('FUSANHE_FEATURE_PRODUCTS is not enabled on this stack.')

    def make_product(self):
        code = unique('PROD')
        s, product = call('POST', '/FusanheProduct', {
            'name': f'糖水黄桃罐头 {code}',
            'nameEn': f'Canned Yellow Peach in Syrup {code}',
            'code': code,
            'category': '水果罐头',
            'defaultMoq': 500,
            'defaultMoqUnit': 'carton',
        })
        self.assertEqual(s, 200, product)
        return product

    def make_spec(self, product_id, version, **overrides):
        payload = {
            'name': f'规格 {version}',
            'productId': product_id,
            'version': version,
            'packingSpec': '425g × 24罐/纸箱',
            'pricingUnit': 'carton',
            'netWeightKg': 10.2,
            'grossWeightKg': 13.5,
            'cartonSpec': '41 × 31 × 22 cm',
            'moq': 500,
            'moqUnit': 'carton',
            'ingredients': '黄桃、水、白砂糖、柠檬酸',
            'allergenStatus': 'none',
            'shelfLife': '36 个月',
            'storageConditions': '常温干燥保存，避免阳光直射',
            'origin': '中国山东',
            'markets': '中东、东南亚',
            'source': '工厂资料 2026-08',
        }
        payload.update(overrides)
        s, spec = call('POST', '/FusanheProductSpec', payload)
        self.assertEqual(s, 200, spec)
        return spec

    def test_spec_review_lifecycle_and_immutability(self):
        product = self.make_product()
        spec = self.make_spec(product['id'], 'v1')
        self.assertEqual(spec['status'], 'draft')
        # Approve via dedicated endpoint.
        s, approved = call('POST', f"/Fusanhe/product-spec/{spec['id']}/approve")
        self.assertEqual(s, 200, approved)
        # Approving twice is a conflict.
        s, err = call('POST', f"/Fusanhe/product-spec/{spec['id']}/approve")
        self.assertEqual(s, 409)
        # Content change after approval is rejected.
        s, err = call('PATCH', f"/FusanheProductSpec/{spec['id']}", {'grossWeightKg': 99})
        self.assertEqual(s, 403, err)
        # Retirement is the only allowed post-approval transition.
        s, retired = call('POST', f"/Fusanhe/product-spec/{spec['id']}/retire")
        self.assertEqual(s, 200, retired)
        s, err = call('POST', f"/Fusanhe/product-spec/{spec['id']}/retire")
        self.assertEqual(s, 409)

    def test_version_history_keeps_approved_versions_readable(self):
        """Referenced historical versions stay retrievable, never overwritten."""
        product = self.make_product()
        v1 = self.make_spec(product['id'], 'v1', netWeightKg=10.2)
        call('POST', f"/Fusanhe/product-spec/{v1['id']}/approve")
        # A "new revision" is a NEW record; the old one is untouched.
        v2 = self.make_spec(product['id'], 'v2', netWeightKg=10.5, allergenStatus='contains',
                            allergens='可能含微量坚果（同生产线）')
        call('POST', f"/Fusanhe/product-spec/{v2['id']}/approve")
        s, v1_after = call('GET', f"/FusanheProductSpec/{v1['id']}")
        self.assertEqual(v1_after['netWeightKg'], 10.2)
        self.assertEqual(v1_after['status'], 'approved')
        s, v2_after = call('GET', f"/FusanheProductSpec/{v2['id']}")
        self.assertEqual(v2_after['netWeightKg'], 10.5)

    def test_duplicate_product_version_rejected(self):
        product = self.make_product()
        self.make_spec(product['id'], 'v1')
        s, err = call('POST', '/FusanheProductSpec', {
            'name': '重复版本', 'productId': product['id'], 'version': 'v1',
        })
        self.assertEqual(s, 409, err)

    def test_unknown_is_not_confused_with_confirmed_absence(self):
        product = self.make_product()
        spec = self.make_spec(product['id'], 'v1', allergenStatus='unknown', allergens=None)
        self.assertEqual(spec['allergenStatus'], 'unknown')
        s, err = call('POST', '/FusanheProductSpec', {
            'name': '坏枚举', 'productId': product['id'], 'version': 'vX',
            'allergenStatus': 'maybe',
        })
        self.assertEqual(s, 400)
        s, err = call('POST', '/FusanheProductSpec', {
            'name': '负MOQ', 'productId': product['id'], 'version': 'vY',
            'moq': -5,
        })
        self.assertEqual(s, 400)

    def test_restricted_user_cannot_approve_specs(self):
        ts = unique('usr')
        username = f'wp1{uuid.uuid4().hex[:10]}'
        s, user = call('POST', '/User', {
            'userName': username, 'lastName': f'WP1 {ts}', 'password': 'Wp1-Restricted-1!',
        })
        self.assertEqual(s, 200, user)
        product = self.make_product()
        spec = self.make_spec(product['id'], 'v1')
        restricted = base64.b64encode(f'{username}:Wp1-Restricted-1!'.encode()).decode()
        s, err = call('POST', f"/Fusanhe/product-spec/{spec['id']}/approve", auth='Basic ' + restricted)
        self.assertEqual(s, 403, err)
        s, err = call('GET', '/FusanheProduct?maxSize=1', auth='Basic ' + restricted)
        self.assertEqual(s, 403, err)


if __name__ == '__main__':
    unittest.main()
