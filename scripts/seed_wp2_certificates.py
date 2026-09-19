#!/usr/bin/env python3
"""Seed synthetic demo certificates (WP2). Idempotent by certificateNo.

    set -a; source .env; set +a
    export ESPOCRM_API_URL=http://localhost:8088/api/v1
    python3 scripts/seed_wp2_certificates.py
"""
import base64
import json
import os
import sys
import urllib.error
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
        with urllib.request.urlopen(req, timeout=20) as r:
            body = r.read().decode()
            return r.status, json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def find_product(code):
    s, r = call('GET', f'/FusanheProduct?maxSize=1&where[0][type]=equals&where[0][attribute]=code&where[0][value]={code}')
    if s == 200 and r.get('total'):
        return r['list'][0]
    return None


CERTS = [
    {'name': 'ISO 22000 食品安全管理体系（工厂级）', 'type': 'iso22000', 'scopeLevel': 'factory',
     'factoryName': '山东XX食品科技有限公司', 'issuer': '演示认证中心', 'certificateNo': 'DEMO-ISO22000-2026',
     'issueDate': UTC_DAY.isoformat(), 'validFrom': UTC_DAY.isoformat(),
     'validTo': (UTC_DAY + timedelta(days=300)).isoformat(), 'markets': '全球通用（演示）', 'approve': True},
    {'name': '清真认证（HALAL）', 'type': 'halal', 'scopeLevel': 'product',
     'issuer': '演示清真认证委员会', 'certificateNo': 'DEMO-HALAL-2026',
     'issueDate': UTC_DAY.isoformat(), 'validFrom': UTC_DAY.isoformat(),
     'validTo': (UTC_DAY + timedelta(days=200)).isoformat(), 'markets': '中东、东南亚', 'approve': True},
    {'name': '第三方检测报告（甜玉米罐头 2026Q3）', 'type': 'testReport', 'scopeLevel': 'product',
     'issuer': '演示检验实验室', 'certificateNo': 'DEMO-TEST-2026Q3',
     'issueDate': UTC_DAY.isoformat(), 'validFrom': UTC_DAY.isoformat(),
     'validTo': (UTC_DAY + timedelta(days=45)).isoformat(), 'markets': '', 'approve': True},
    {'name': '出口卫生证书（批次级示例）', 'type': 'healthCertificate', 'scopeLevel': 'batch',
     'batchCode': 'DEMO-BATCH-20260901', 'issuer': '演示海关', 'certificateNo': 'DEMO-HEALTH-BATCH01',
     'issueDate': (UTC_DAY - timedelta(days=10)).isoformat(), 'validFrom': (UTC_DAY - timedelta(days=10)).isoformat(),
     'validTo': (UTC_DAY - timedelta(days=1)).isoformat(), 'markets': '', 'approve': True},
    {'name': '犹太认证（Kosher，申请中，未审核）', 'type': 'kosher', 'scopeLevel': 'product',
     'issuer': '演示犹太认证机构', 'certificateNo': 'DEMO-KOSHER-PENDING',
     'issueDate': UTC_DAY.isoformat(), 'validFrom': UTC_DAY.isoformat(),
     'validTo': (UTC_DAY + timedelta(days=365)).isoformat(), 'markets': '', 'approve': False},
]


def main():
    created, approved = 0, 0
    for c in CERTS:
        s, r = call('GET', f"/FusanheCertificate?maxSize=1&where[0][type]=equals&where[0][attribute]=certificateNo&where[0][value]={c['certificateNo']}")
        if s == 200 and r.get('total'):
            continue
        product = find_product('DEMO-CANNED-SWEETCORN')
        payload = {k: v for k, v in c.items() if k != 'approve'}
        if c.get('scopeLevel') == 'product' and product:
            payload['productId'] = product['id']
        s, created_cert = call('POST', '/FusanheCertificate', payload)
        if s != 200:
            print(f'failed: {c["certificateNo"]}: {created_cert}')
            sys.exit(1)
        created += 1
        if c.get('approve'):
            s, out = call('POST', f"/Fusanhe/certificate/{created_cert['id']}/approve")
            if s == 200:
                approved += 1
    print(json.dumps({'created': created, 'approved': approved}, ensure_ascii=False))


if __name__ == '__main__':
    main()
