#!/usr/bin/env python3
"""Seed synthetic demo samples (WP3). Idempotent by sample name marker.

    set -a; source .env; set +a
    export ESPOCRM_API_URL=http://localhost:8088/api/v1
    python3 scripts/seed_wp3_samples.py
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

DEMO = [
    {'name': 'DEMO-样品-黄桃罐头-迪拜GulfFoods', 'flow': 'closed',
     'feedback': '客户收到后反馈糖水色泽和果肉完整度不错，要求报 2×40HQ 年度框架价。', 'result': 'positive',
     'tracking': 'DEMO-TRK-PEACH-001', 'carrier': 'DHL'},
    {'name': 'DEMO-样品-甜玉米-马尼拉ManilaFoods', 'flow': 'sent',
     'tracking': 'DEMO-TRK-CORN-002', 'carrier': 'FedEx',
     'exception': '清关文件补充中，客户要求暂存机场。'},
    {'name': 'DEMO-样品-方便面OEM-吉达AlNoor', 'flow': 'cancelled',
     'reason': '客户暂缓 OEM 项目，转为代理现有品牌。'},
]


def call(method, path, data=None):
    req = urllib.request.Request(BASE + path, json.dumps(data).encode() if data is not None else None, H, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            body = r.read().decode()
            return r.status, json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def find_sample(name):
    s, r = call('GET', f'/FusanheSample?maxSize=1&where[0][type]=equals&where[0][attribute]=name&where[0][value]={urllib.request.quote(name)}')
    if s == 200 and r.get('total'):
        return r['list'][0]
    return None


def main():
    created = 0
    for item in DEMO:
        if find_sample(item['name']):
            continue
        payload = {
            'name': item['name'],
            'quantity': 1, 'unit': 'carton',
            'feeAmount': 60, 'feeCurrency': 'USD',
            'recipientName': 'Demo Receiver',
            'recipientAddress': 'Demo address',
            'expectedSendDate': UTC_DAY.isoformat(),
        }
        s, sample = call('POST', '/FusanheSample', payload)
        if s != 200:
            print(f'failed: {item["name"]}: {sample}')
            sys.exit(1)
        created += 1
        sid = sample['id']
        flow = item['flow']
        call('POST', f'/Fusanhe/sample/{sid}/prepare')
        if flow in ('sent', 'closed'):
            call('POST', f'/Fusanhe/sample/{sid}/send', {
                'trackingNo': item['tracking'], 'carrier': item['carrier'],
                'sentAt': UTC_DAY.isoformat(),
            })
        if item.get('exception'):
            call('POST', f'/Fusanhe/sample/{sid}/exception', {'note': item['exception']})
        if flow == 'closed':
            call('POST', f'/Fusanhe/sample/{sid}/deliver', {'deliveredAt': UTC_DAY.isoformat()})
            call('POST', f'/Fusanhe/sample/{sid}/feedback', {
                'feedback': item['feedback'], 'feedbackResult': item['result'],
            })
            call('POST', f'/Fusanhe/sample/{sid}/close')
        if flow == 'cancelled':
            call('POST', f'/Fusanhe/sample/{sid}/cancel', {'reason': item['reason']})
    print(json.dumps({'created': created}, ensure_ascii=False))


if __name__ == '__main__':
    main()
