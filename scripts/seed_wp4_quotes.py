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
