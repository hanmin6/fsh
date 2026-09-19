#!/usr/bin/env python3
"""Seed synthetic demo inquiries and quotes (WP4). Idempotent by name.

    set -a; source .env; set +a
    export ESPOCRM_API_URL=http://localhost:8088/api/v1
    python3 scripts/seed_wp4_quotes.py
"""
import base64
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

BASE = os.getenv('ESPOCRM_API_URL', 'http://localhost:8080/api/v1').rstrip('/')
H = {'Authorization': 'Basic ' + base64.b64encode(
    f"{os.environ['ESPOCRM_ADMIN_USERNAME']}:{os.environ['ESPOCRM_ADMIN_PASSWORD']}".encode()
).decode(), 'Content-Type': 'application/json'}
UTC_DAY = datetime.now(timezone.utc).date()


def call(method, path, data=None):
    req = urllib.request.Request(BASE + path, json.dumps(data).encode() if data is not None else None, H, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            body = r.read().decode()
            return r.status, json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def find(scope, attribute, value):
    q = urllib.parse.urlencode({'where[0][type]': 'equals', 'where[0][attribute]': attribute, 'where[0][value]': value})
    s, r = call('GET', f'/{scope}?{q}&maxSize=1')
    if s == 200 and r.get('total'):
        return r['list'][0]
    return None


def main():
    # Demo customer
    account = find('Account', 'name', 'Gulf Foods Trading LLC（演示）')
    if not account:
        s, account = call('POST', '/Account', {'name': 'Gulf Foods Trading LLC（演示）', 'billingAddressCountry': 'United Arab Emirates'})
        assert s == 200, account

    # Inquiry (intentionally incomplete for the missing-info demo)
    inquiry = find('FusanheInquiry', 'name', 'DEMO-询价-甜玉米 2×40HQ 迪拜')
    if not inquiry:
        product = find('FusanheProduct', 'code', 'DEMO-CANNED-SWEETCORN')
        s, inquiry = call('POST', '/FusanheInquiry', {
            'name': 'DEMO-询价-甜玉米 2×40HQ 迪拜',
            'accountId': account['id'],
            'productId': product['id'] if product else None,
            'quantity': 2, 'unit': 'container40',
            'destination': 'Jebel Ali, UAE',
            'certificatesNeeded': 'Halal、第三方检测报告',
            'notes': '客户月均 2 柜，要求报 CIF 价格。',
        })
        assert s == 200, inquiry

    # Quote v1 -> approved -> accepted (immutable snapshot demo)
    quote = find('FusanheQuote', 'name', 'DEMO-报价-甜玉米 迪拜 2026Q4')
    if not quote:
        s, quote = call('POST', '/FusanheQuote', {
            'name': 'DEMO-报价-甜玉米 迪拜 2026Q4',
            'accountId': account['id'],
            'inquiryId': inquiry['id'],
            'currency': 'USD',
            'validUntil': (UTC_DAY + timedelta(days=45)).isoformat(),
            'tradeTerm': 'CIF', 'tradeTermPlace': 'Jebel Ali, UAE', 'tradeTermVersion': 'Incoterms 2020',
            'paymentTerms': '30% T/T 预付，70% 见提单副本（演示记录）',
            'leadTimeText': '预付款到账后 25 天内装运',
            'exchangeRate': 7.12, 'exchangeRateDate': UTC_DAY.isoformat(), 'exchangeRateSource': '人工录入（演示）',
            'notesInternal': '内部演示数据：成本由工厂确认后再复核。',
        })
        assert s == 200, quote
        corn = find('FusanheProduct', 'code', 'DEMO-CANNED-SWEETCORN')
        s, item = call('POST', '/FusanheQuoteItem', {
            'quoteId': quote['id'], 'position': 1,
            'productId': corn['id'] if corn else None,
            'description': 'Canned sweet corn kernels 340g x 24',
            'quantity': 1600, 'unit': 'carton', 'unitPrice': 9.85,
            'moq': 800, 'packingSpec': '340g × 24罐/纸箱',
            'leadTimeText': '分两批装运', 'remark': '价格有效期以报价单为准',
        })
        assert s == 200, item
        call('POST', f"/Fusanhe/quote/{quote['id']}/submit")
        call('POST', f"/Fusanhe/quote/{quote['id']}/approve")
        call('POST', f"/Fusanhe/quote/{quote['id']}/accept",
             {'acceptedByRef': 'Maria Santos（邮件确认，演示）', 'acceptedAt': UTC_DAY.isoformat()})
        # Revision chain demo: v2 draft copied from accepted v1
        s, rev = call('POST', f"/Fusanhe/quote/{quote['id']}/copy-revision",
                      {'note': '演示：客户询问 LCL 拼柜可能性，v2 重新核算。'})
        assert s == 200, rev

    print(json.dumps({'ok': True, 'accountId': account['id'], 'inquiryId': inquiry['id'], 'quoteId': quote['id']}, ensure_ascii=False))


if __name__ == '__main__':
    main()

# ---------------------------------------------------------------------------
# WP7 demo: create a confirmed order with shipments from the accepted quote.
# Kept in this script so a single seed run provisions the whole quote->order chain.
def seed_order():
    from datetime import timedelta as _td
    quote = None
    q = urllib.parse.urlencode({'where[0][type]': 'equals', 'where[0][attribute]': 'name', 'where[0][value]': 'DEMO-报价-甜玉米 迪拜 2026Q4'})
    s, r = call('GET', f'/FusanheQuote?{q}&maxSize=10')
    if s == 200:
        for candidate in r.get('list', []):
            if candidate.get('status') == 'accepted':
                quote = candidate
                break
    if not quote:
        print(json.dumps({'order': 'skipped: accepted demo quote not found'}))
        return
    existing = find('FusanheSalesOrder', 'name', 'DEMO-订单-甜玉米 迪拜 2026Q4')
    if existing:
        return
    s, order = call('POST', f"/Fusanhe/quote/{quote['id']}/create-order", {
        'name': 'DEMO-订单-甜玉米 迪拜 2026Q4',
        'customerRequiredDate': (UTC_DAY + _td(days=60)).isoformat(),
    })
    assert s == 200, order
    s, r = call('POST', f"/Fusanhe/order/{order['id']}/confirm",
                {'internalConfirmedDate': (UTC_DAY + _td(days=50)).isoformat()})
    assert s == 200, r
    s, lines = call('GET', f"/FusanheOrderLine?maxSize=5&where[0][type]=equals&where[0][attribute]=orderId&where[0][value]={order['id']}")
    line = lines['list'][0]
    s, shp = call('POST', '/FusanheOrderShipment', {
        'name': '首批 60%', 'orderId': order['id'], 'sequence': 1,
        'plannedShipDate': (UTC_DAY + _td(days=25)).isoformat(),
        'plannedArrivalDate': (UTC_DAY + _td(days=40)).isoformat(),
    })
    s, si = call('POST', '/FusanheShipmentItem', {
        'shipmentId': shp['id'], 'orderLineId': line['id'],
        'quantity': 960, 'unit': 'carton', 'batchCode': 'DEMO-BATCH-SO01',
    })
    assert s == 200, si
    print(json.dumps({'order': order['id'], 'firstShipment': shp['id']}))


seed_order()
