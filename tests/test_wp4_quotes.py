"""WP4: inquiries, quotes and PI drafts (feature-flagged module).

Covers the review/acceptance workflow, versioning and immutable accepted
snapshots, single-currency totals with server-side rounding, customer-safe
print output, inquiry missing-info checklist and ACL.
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


def call(method, path, data=None, auth=None, raw=False):
    headers = {'Content-Type': 'application/json', 'Authorization': auth or ('Basic ' + ADMIN)}
    req = urllib.request.Request(
        BASE + path,
        json.dumps(data).encode() if data is not None else None,
        headers, method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            body = r.read().decode()
            if raw:
                return r.status, body
            return r.status, json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        if raw:
            return e.code, body
        try:
            return e.code, json.loads(body)
        except json.JSONDecodeError:
            return e.code, body


def unique(prefix):
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


class WP4Quotes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        s, features = call('GET', '/Fusanhe/features')
        if s != 200 or not features.get('features', {}).get('quotes'):
            raise unittest.SkipTest('FUSANHE_FEATURE_QUOTES is not enabled on this stack.')
        s, account = call('POST', '/Account', {'name': unique('Quote Buyer'), 'billingAddressCountry': 'United Arab Emirates'})
        assert s == 200, account
        cls.account = account

    def make_quote(self, **overrides):
        payload = {
            'name': f'报价 {unique("QT")}',
            'accountId': self.account['id'],
            'currency': 'USD',
            'tradeTerm': 'FOB',
            'tradeTermPlace': 'Qingdao, China',
            'tradeTermVersion': 'Incoterms 2020',
            'paymentTerms': '30% 预付 + 70% 见提单副本（演示记录）',
            'leadTimeText': '收到预付款后 30 天内交货',
            'validUntil': '2027-03-31',
            'exchangeRate': 7.12,
            'exchangeRateDate': '2026-09-20',
            'exchangeRateSource': '中行折算价（人工录入演示）',
        }
        payload.update(overrides)
        s, quote = call('POST', '/FusanheQuote', payload)
        self.assertEqual(s, 200, quote)
        self.assertTrue(quote['number'])
        self.assertEqual(quote['versionNo'], 1)
        self.assertTrue(quote['rootId'])
        return quote

    def add_item(self, quote_id, **overrides):
        payload = {
            'quoteId': quote_id,
            'position': 1,
            'description': 'Canned yellow peach halves 425g x 24',
            'quantity': 500,
            'unit': 'carton',
            'unitPrice': 8.455,
        }
        payload.update(overrides)
        s, item = call('POST', '/FusanheQuoteItem', payload)
        self.assertEqual(s, 200, item)
        return item

    def test_amount_computed_with_single_rounding_rule(self):
        quote = self.make_quote()
        item = self.add_item(quote['id'], quantity=500, unitPrice=8.455)
        # 500 * 8.455 = 4227.5 exactly; half-up at 2 decimals is server-defined.
        self.assertEqual(round(item['amount'], 2), 4227.5)
        item2 = self.add_item(quote['id'], position=2, quantity=3, unitPrice=1.115)
        self.assertEqual(round(item2['amount'], 2), 3.35)  # 3.345 -> 3.35 half-up
        s, summary = call('GET', f"/Fusanhe/quote/{quote['id']}/print")
        self.assertEqual(s, 200, summary)
        self.assertEqual(summary['totalAmount'], 4230.85)

    def test_full_quote_workflow_and_accept_snapshot(self):
        quote = self.make_quote()
        qid = quote['id']
        # Cannot approve without items.
        s, err = call('POST', f'/Fusanhe/quote/{qid}/submit')
        self.assertEqual(s, 409, err)
        self.add_item(qid)
        # Accepting before approval is refused.
        s, err = call('POST', f'/Fusanhe/quote/{qid}/accept', {'acceptedByRef': 'buyer'})
        self.assertEqual(s, 409, err)
        s, r = call('POST', f'/Fusanhe/quote/{qid}/submit')
        self.assertEqual(r['status'], 'inReview')
        s, r = call('POST', f'/Fusanhe/quote/{qid}/approve')
        self.assertEqual(r['status'], 'approved')
        # Generic PATCH cannot forge status.
        s, err = call('PATCH', f'/FusanheQuote/{qid}', {'status': 'accepted'})
        self.assertEqual(s, 403, err)
        s, r = call('POST', f'/Fusanhe/quote/{qid}/accept',
                    {'acceptedByRef': 'Amina Yusuf (email confirmation)', 'acceptedAt': '2026-09-20'})
        self.assertEqual(r['status'], 'accepted')
        # Accepted snapshot is immutable.
        s, err = call('PATCH', f'/FusanheQuote/{qid}', {'validUntil': '2028-01-01'})
        self.assertEqual(s, 403, err)
        s, err = call('POST', '/FusanheQuoteItem', {'quoteId': qid, 'position': 2,
                                                    'quantity': 1, 'unit': 'carton', 'unitPrice': 1})
        self.assertEqual(s, 409, err)

    def test_copy_revision_chain(self):
        quote = self.make_quote()
        self.add_item(quote['id'])
        call('POST', f"/Fusanhe/quote/{quote['id']}/submit")
        call('POST', f"/Fusanhe/quote/{quote['id']}/approve")
        s, rev = call('POST', f"/Fusanhe/quote/{quote['id']}/copy-revision",
                      {'note': '客户要求 CIF 改报，v2'})
        self.assertEqual(s, 200, rev)
        self.assertEqual(rev['versionNo'], 2)
        s, original = call('GET', f"/FusanheQuote/{quote['id']}")
        self.assertEqual(original['status'], 'superseded')
        s, revision = call('GET', f"/FusanheQuote/{rev['id']}")
        self.assertEqual(revision['status'], 'draft')
        self.assertEqual(revision['versionNo'], 2)
        self.assertEqual(revision['rootId'], quote['rootId'])
        # Lines copied.
        s, items = call('GET', f"/FusanheQuoteItem?maxSize=20&where[0][type]=equals&where[0][attribute]=quoteId&where[0][value]={rev['id']}")
        self.assertEqual(items['total'], 1)
        # Accepted quotes are NOT superseded by a revision (snapshot preserved).
        call('POST', f"/Fusanhe/quote/{rev['id']}/submit")
        call('POST', f"/Fusanhe/quote/{rev['id']}/approve")
        call('POST', f"/Fusanhe/quote/{rev['id']}/accept", {'acceptedByRef': 'buyer'})
        s, rev3 = call('POST', f"/Fusanhe/quote/{rev['id']}/copy-revision", {'note': 'v3'})
        self.assertEqual(rev3['versionNo'], 3)
        s, accepted_quote = call('GET', f"/FusanheQuote/{rev['id']}")
        self.assertEqual(accepted_quote['status'], 'accepted',
                         'Accepted snapshot must remain accepted.')

    def test_print_output_is_customer_safe(self):
        quote = self.make_quote(notesInternal='成本 6.2 USD/箱，利润率约 20%，切勿外泄')
        self.add_item(quote['id'], internalNote='供应商山东XX，出厂价 6.2')
        s, data = call('GET', f"/Fusanhe/quote/{quote['id']}/print?kind=pi")
        self.assertEqual(s, 200, data)
        self.assertTrue(data['draft'])
        self.assertIn('DRAFT', data['title'])
        blob = json.dumps(data, ensure_ascii=False)
        self.assertNotIn('6.2', blob)
        self.assertNotIn('利润率', blob)
        self.assertNotIn('山东XX', blob)
        self.assertNotIn('internalNote', blob)
        # HTML rendering also stays customer-safe.
        s, html = call('GET', f"/Fusanhe/quote/{quote['id']}/html?kind=quotation", raw=True)
        self.assertEqual(s, 200)
        self.assertIn('DRAFT', html)
        self.assertNotIn('6.2', html)
        self.assertNotIn('利润率', html)
        self.assertNotIn('山东XX', html)

    def test_inquiry_missing_checklist(self):
        s, inquiry = call('POST', '/FusanheInquiry', {
            'name': f'询价 {unique("INQ")}',
            'accountId': self.account['id'],
            'quantity': 2,
            'unit': 'container40',
            'destination': 'Jebel Ali, UAE',
        })
        self.assertEqual(s, 200, inquiry)
        s, missing = call('GET', f"/Fusanhe/inquiry/{inquiry['id']}/missing")
        self.assertEqual(s, 200, missing)
        self.assertFalse(missing['complete'])
        self.assertIn('交期要求', missing['missing'])
        self.assertIn('包装要求', missing['missing'])
        self.assertIn('产品', missing['missing'])
        # Fill everything in: complete=True.
        product_code = unique('PROD')
        s, product = call('POST', '/FusanheProduct', {'name': product_code, 'code': product_code})
        s, upd = call('PATCH', f"/FusanheInquiry/{inquiry['id']}", {
            'productId': product['id'],
            'deliveryWindow': '2026年12月前',
            'packagingRequirement': '出口纸箱',
            'certificatesNeeded': 'Halal',
        })
        s, missing = call('GET', f"/Fusanhe/inquiry/{inquiry['id']}/missing")
        self.assertTrue(missing['complete'], missing)

    def test_restricted_user_cannot_approve_quotes(self):
        username = f'wp4{uuid.uuid4().hex[:10]}'
        s, user = call('POST', '/User', {
            'userName': username, 'lastName': f'WP4 {unique("u")}', 'password': 'Wp4-Restricted-1!',
        })
        self.assertEqual(s, 200, user)
        quote = self.make_quote()
        restricted = base64.b64encode(f'{username}:Wp4-Restricted-1!'.encode()).decode()
        s, err = call('POST', f'/Fusanhe/quote/{quote["id"]}/approve', auth='Basic ' + restricted)
        self.assertEqual(s, 403, err)
        s, err = call('GET', f'/Fusanhe/quote/{quote["id"]}/print', auth='Basic ' + restricted)
        self.assertEqual(s, 403, err)


if __name__ == '__main__':
    unittest.main()
