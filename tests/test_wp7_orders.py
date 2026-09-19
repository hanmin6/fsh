"""WP7: lightweight sales orders and deliveries (feature-flagged).

Covers order-from-accepted-quote snapshots, customer vs internal delivery
dates, shipment quantity validation (no over-shipment, unit match, cancelled
shipments excluded), completion gating, batch traceability and ACL.
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


class WP7Orders(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        s, features = call('GET', '/Fusanhe/features')
        if s != 200 or not features.get('features', {}).get('orders'):
            raise unittest.SkipTest('FUSANHE_FEATURE_ORDERS is not enabled on this stack.')

    def make_accepted_quote(self):
        s, account = call('POST', '/Account', {'name': unique('Order Buyer'), 'billingAddressCountry': 'Philippines'})
        self.assertEqual(s, 200, account)
        s, quote = call('POST', '/FusanheQuote', {
            'name': f'订单源报价 {unique("Q")}',
            'accountId': account['id'],
            'currency': 'USD',
            'tradeTerm': 'CIF', 'tradeTermPlace': 'Manila', 'tradeTermVersion': 'Incoterms 2020',
            'paymentTerms': '演示付款记录', 'leadTimeText': '预付后 20 天',
            'acceptedByRef': None,
        })
        self.assertEqual(s, 200, quote)
        s, item = call('POST', '/FusanheQuoteItem', {
            'quoteId': quote['id'], 'position': 1,
            'description': 'Instant noodles 85g x 24',
            'quantity': 1000, 'unit': 'ctn', 'unitPrice': 12.5, 'packingSpec': '85g×24/箱',
        })
        self.assertEqual(s, 200, item)
        call('POST', f"/Fusanhe/quote/{quote['id']}/submit")
        call('POST', f"/Fusanhe/quote/{quote['id']}/approve")
        s, r = call('POST', f"/Fusanhe/quote/{quote['id']}/accept",
                    {'acceptedByRef': 'buyer (demo)', 'acceptedAt': '2026-09-20'})
        self.assertEqual(r['status'], 'accepted')
        return quote, item, account

    def make_order(self):
        quote, item, account = self.make_accepted_quote()
        s, order = call('POST', f"/Fusanhe/quote/{quote['id']}/create-order",
                        {'customerRequiredDate': '2026-12-15', 'name': f'DEMO 订单 {unique("O")}'})
        self.assertEqual(s, 200, order)
        s, order = call('GET', f"/FusanheSalesOrder/{order['id']}")
        self.assertEqual(s, 200, order)
        return order, quote, item, account

    def test_order_only_from_accepted_quote(self):
        s, account = call('POST', '/Account', {'name': unique('No Accept')})
        s, quote = call('POST', '/FusanheQuote', {
            'name': f'未接受报价 {unique("Q")}', 'accountId': account['id'], 'currency': 'USD',
        })
        s, err = call('POST', f"/Fusanhe/quote/{quote['id']}/create-order",
                      {'customerRequiredDate': '2026-12-01'})
        self.assertEqual(s, 409, err)
        s, err = call('POST', f"/Fusanhe/quote/{quote['id']}/create-order", {})
        self.assertEqual(s, 409, err)

    def test_snapshot_and_separate_delivery_dates(self):
        order, quote, item, account = self.make_order()
        # Snapshot fields copied from the quote.
        self.assertEqual(order['currency'], 'USD')
        self.assertEqual(order['quoteAcceptedByRef'], 'buyer (demo)')
        s, lines = call('GET', f"/FusanheOrderLine?maxSize=10&where[0][type]=equals&where[0][attribute]=orderId&where[0][value]={order['id']}")
        self.assertEqual(lines['total'], 1)
        line = lines['list'][0]
        self.assertEqual(line['quantity'], 1000)
        self.assertEqual(line['unitPrice'], 12.5)
        self.assertEqual(line['amount'], 12500.0)
        # Customer-required and internal-confirmed dates are separate fields.
        self.assertEqual(order['customerRequiredDate'], '2026-12-15')
        self.assertIsNone(order['internalConfirmedDate'])
        s, err = call('POST', f"/Fusanhe/order/{order['id']}/confirm", {})
        self.assertEqual(s, 400, 'Confirm without internal date must fail.')
        s, r = call('POST', f"/Fusanhe/order/{order['id']}/confirm", {'internalConfirmedDate': '2026-12-05'})
        self.assertEqual(r['status'], 'confirmed')
        s, ent = call('GET', f"/FusanheSalesOrder/{order['id']}")
        self.assertEqual(ent['internalConfirmedDate'], '2026-12-05')
        self.assertEqual(ent['customerRequiredDate'], '2026-12-15')
        # Confirmed snapshot is frozen for generic edits.
        s, err = call('PATCH', f"/FusanheSalesOrder/{order['id']}", {'paymentTerms': 'tampered'})
        self.assertEqual(s, 403, err)
        s, err = call('PATCH', f"/FusanheOrderLine/{line['id']}", {'quantity': 99999})
        self.assertEqual(s, 403, err)

    def test_shipment_quantity_validation(self):
        order, quote, item, account = self.make_order()
        call('POST', f"/Fusanhe/order/{order['id']}/confirm", {'internalConfirmedDate': '2026-12-05'})
        s, lines = call('GET', f"/FusanheOrderLine?maxSize=10&where[0][type]=equals&where[0][attribute]=orderId&where[0][value]={order['id']}")
        line = lines['list'][0]
        # First shipment: 600 of 1000 ctn.
        s, shp1 = call('POST', '/FusanheOrderShipment', {
            'name': '首批', 'orderId': order['id'], 'sequence': 1,
            'plannedShipDate': '2026-11-20', 'plannedArrivalDate': '2026-12-10',
        })
        self.assertEqual(s, 200, shp1)
        s, si1 = call('POST', '/FusanheShipmentItem', {
            'shipmentId': shp1['id'], 'orderLineId': line['id'],
            'quantity': 600, 'unit': 'ctn', 'batchCode': unique('BATCH'),
        })
        self.assertEqual(s, 200, si1)
        # Second shipment: 500 more would over-ship (600 + 500 > 1000).
        s, shp2 = call('POST', '/FusanheOrderShipment', {'name': '尾批', 'orderId': order['id'], 'sequence': 2})
        s, err = call('POST', '/FusanheShipmentItem', {
            'shipmentId': shp2['id'], 'orderLineId': line['id'],
            'quantity': 500, 'unit': 'ctn',
        })
        self.assertEqual(s, 409, err)
        # Unit mismatch is rejected.
        s, err = call('POST', '/FusanheShipmentItem', {
            'shipmentId': shp2['id'], 'orderLineId': line['id'],
            'quantity': 100, 'unit': 'kg',
        })
        self.assertEqual(s, 409, err)
        # Exactly 400 more is fine.
        s, si2 = call('POST', '/FusanheShipmentItem', {
            'shipmentId': shp2['id'], 'orderLineId': line['id'], 'quantity': 400, 'unit': 'ctn',
        })
        self.assertEqual(s, 200, si2)
        # Ship and arrive with actual dates.
        s, r = call('POST', f"/Fusanhe/shipment/{shp1['id']}/ship", {'actualShipDate': '2026-11-21'})
        self.assertEqual(r['status'], 'shipped')
        s, r = call('POST', f"/Fusanhe/shipment/{shp1['id']}/arrive", {'actualArrivalDate': '2026-12-09'})
        self.assertEqual(r['status'], 'arrived')
        # Order cannot complete while a shipment is planned.
        s, err = call('POST', f"/Fusanhe/order/{order['id']}/complete")
        self.assertEqual(s, 409, err)
        # 600 + 400 = 1000 shipped in total; anything more must be rejected.
        s, shp3 = call('POST', '/FusanheOrderShipment', {'name': '补批', 'orderId': order['id'], 'sequence': 3})
        s, err = call('POST', '/FusanheShipmentItem', {
            'shipmentId': shp3['id'], 'orderLineId': line['id'], 'quantity': 100, 'unit': 'ctn',
        })
        self.assertEqual(s, 409, err)
        # Cancelling the planned shp2 removes its 400 from the shipped total,
        # so the same 400 can now be booked on the new shipment.
        call('POST', f"/Fusanhe/shipment/{shp2['id']}/cancel")
        s, si3 = call('POST', '/FusanheShipmentItem', {
            'shipmentId': shp3['id'], 'orderLineId': line['id'], 'quantity': 400, 'unit': 'ctn',
        })
        self.assertEqual(s, 200, si3)
        call('POST', f"/Fusanhe/shipment/{shp3['id']}/ship")
        call('POST', f"/Fusanhe/shipment/{shp3['id']}/arrive")
        s, r = call('POST', f"/Fusanhe/order/{order['id']}/complete")
        self.assertEqual(r['status'], 'completed')

    def test_batch_traceability(self):
        order, quote, item, account = self.make_order()
        call('POST', f"/Fusanhe/order/{order['id']}/confirm", {'internalConfirmedDate': '2026-12-05'})
        s, lines = call('GET', f"/FusanheOrderLine?maxSize=10&where[0][type]=equals&where[0][attribute]=orderId&where[0][value]={order['id']}")
        line = lines['list'][0]
        batch = unique('TRACE')
        s, shp = call('POST', '/FusanheOrderShipment', {'name': '溯源批', 'orderId': order['id']})
        s, si = call('POST', '/FusanheShipmentItem', {
            'shipmentId': shp['id'], 'orderLineId': line['id'], 'quantity': 100, 'unit': 'ctn',
            'batchCode': batch,
        })
        s, r = call('GET', f'/Fusanhe/orders/by-batch?batch={batch}')
        self.assertEqual(s, 200, r)
        self.assertEqual(r['total'], 1)
        self.assertEqual(r['list'][0]['orderId'], order['id'])
        self.assertEqual(r['list'][0]['accountId'], account['id'])

    def test_restricted_user_cannot_create_orders(self):
        username = f'wp7{uuid.uuid4().hex[:10]}'
        s, user = call('POST', '/User', {
            'userName': username, 'lastName': f'WP7 {unique("u")}', 'password': 'Wp7-Restricted-1!',
        })
        self.assertEqual(s, 200, user)
        quote, item, account = self.make_accepted_quote()
        restricted = base64.b64encode(f'{username}:Wp7-Restricted-1!'.encode()).decode()
        s, err = call('POST', f"/Fusanhe/quote/{quote['id']}/create-order",
                      {'customerRequiredDate': '2026-12-01'}, auth='Basic ' + restricted)
        self.assertEqual(s, 403, err)


if __name__ == '__main__':
    unittest.main()
