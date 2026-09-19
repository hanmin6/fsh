#!/usr/bin/env python3
"""Seed synthetic demo data for the industry modules (WP1 products first).

Idempotent: products are matched by code, spec versions by (product, version).
Run against the isolated test stack only:

    set -a; source .env; set +a
    export ESPOCRM_API_URL=http://localhost:8088/api/v1
    python3 scripts/seed_p1_demo.py
"""
import base64
import json
import os
import sys
import urllib.error
import urllib.request

BASE = os.getenv('ESPOCRM_API_URL', 'http://localhost:8080/api/v1').rstrip('/')
AUTH = 'Basic ' + base64.b64encode(
    f"{os.environ['ESPOCRM_ADMIN_USERNAME']}:{os.environ['ESPOCRM_ADMIN_PASSWORD']}".encode()
).decode()
H = {'Authorization': AUTH, 'Content-Type': 'application/json'}


def call(method, path, data=None):
    req = urllib.request.Request(
        BASE + path,
        json.dumps(data).encode() if data is not None else None,
        H, method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            body = r.read().decode()
            return r.status, json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def find(scope, attribute, value):
    import urllib.parse
    q = urllib.parse.urlencode({f'where[0][type]': 'equals', f'where[0][attribute]': attribute, f'where[0][value]': value})
    s, r = call('GET', f'/{scope}?{q}&maxSize=1')
    if s != 200:
        return None
    items = r.get('list', [])
    return items[0] if items else None


PRODUCTS = [
    {
        'code': 'DEMO-CANNED-PEACH',
        'name': '糖水黄桃罐头（对半）',
        'nameEn': 'Canned Yellow Peach Halves in Light Syrup',
        'category': '水果罐头',
        'defaultMoq': 500, 'defaultMoqUnit': 'carton',
        'specs': [
            {
                'version': 'v1', 'name': '标准版 425g×24',
                'packingSpec': '425g × 24罐/纸箱', 'pricingUnit': 'carton',
                'netWeightKg': 10.2, 'grossWeightKg': 13.6, 'cartonSpec': '41 × 31 × 22 cm',
                'moq': 500, 'moqUnit': 'carton',
                'ingredients': '黄桃、水、白砂糖、柠檬酸',
                'allergenStatus': 'none',
                'shelfLife': '36 个月', 'storageConditions': '常温干燥保存，避免阳光直射',
                'origin': '中国山东', 'markets': '中东、东南亚、非洲',
                'source': '工厂资料 2026-08', 'approve': True,
                'customerVisibleNotes': '符合出口标准，可提供形式发票与装箱单。',
                'internalNotes': '合作工厂：山东XX食品；出厂价区间 8.2-8.6 USD/箱。',
            },
        ],
    },
    {
        'code': 'DEMO-CANNED-SWEETCORN',
        'name': '甜玉米粒罐头',
        'nameEn': 'Canned Sweet Corn Kernels',
        'category': '蔬菜罐头',
        'defaultMoq': 800, 'defaultMoqUnit': 'carton',
        'specs': [
            {
                'version': 'v1', 'name': '标准版 340g×24',
                'packingSpec': '340g × 24罐/纸箱', 'pricingUnit': 'carton',
                'netWeightKg': 8.16, 'grossWeightKg': 11.4, 'cartonSpec': '38 × 29 × 22 cm',
                'moq': 800, 'moqUnit': 'carton',
                'ingredients': '甜玉米粒、水、白砂糖、食盐',
                'allergenStatus': 'none',
                'shelfLife': '36 个月', 'storageConditions': '常温干燥保存',
                'origin': '中国吉林', 'markets': '中东、非洲',
                'source': '工厂资料 2026-07', 'approve': True,
                'customerVisibleNotes': '整年供货稳定，可拼柜。',
                'internalNotes': '旺季价格波动大，报价前需向工厂确认。',
            },
            {
                'version': 'v2', 'name': '试制版 340g×24（犹太认证在办）',
                'packingSpec': '340g × 24罐/纸箱', 'pricingUnit': 'carton',
                'netWeightKg': 8.16, 'grossWeightKg': 11.4, 'cartonSpec': '38 × 29 × 22 cm',
                'moq': 1000, 'moqUnit': 'carton',
                'ingredients': '甜玉米粒、水、白砂糖、食盐',
                'allergenStatus': 'unknown',
                'allergens': None,
                'shelfLife': '36 个月', 'storageConditions': '常温干燥保存',
                'origin': '中国吉林', 'markets': '待定',
                'source': '内部试制 2026-09', 'approve': False,
                'customerVisibleNotes': None,
                'internalNotes': '犹太认证申请中，未获批前不得向客户承诺。',
            },
        ],
    },
    {
        'code': 'DEMO-NOODLE-INSTANT',
        'name': '方便面（袋装）',
        'nameEn': 'Instant Noodles (Bag Pack)',
        'category': '方便食品',
        'defaultMoq': 2000, 'defaultMoqUnit': 'ctn',
        'specs': [
            {
                'version': 'v1', 'name': 'OEM 基础版 85g×24',
                'packingSpec': '85g × 24包/箱', 'pricingUnit': 'ctn',
                'netWeightKg': 2.04, 'grossWeightKg': 3.4, 'cartonSpec': '44 × 34 × 30 cm',
                'moq': 2000, 'moqUnit': 'ctn',
                'ingredients': '小麦粉、棕榈油、淀粉、食盐、调味料（含大豆、小麦制品）',
                'allergenStatus': 'contains',
                'allergens': '含小麦、大豆；生产线同时处理含蛋、花生产品',
                'shelfLife': '6 个月', 'storageConditions': '阴凉干燥，避免重压',
                'origin': '中国河南', 'markets': '东南亚、中东',
                'source': '工厂资料 2026-09', 'approve': True,
                'customerVisibleNotes': '支持 OEM 包装与客户品牌，标签可按目标市场定制。',
                'internalNotes': 'OEM 起订量以包装厂排产为准。',
            },
        ],
    },
]


def main():
    created_products, created_specs, approved = 0, 0, 0
    for p in PRODUCTS:
        existing = find('FusanheProduct', 'code', p['code'])
        if existing:
            product_id = existing['id']
        else:
            s, product = call('POST', '/FusanheProduct', {
                'code': p['code'], 'name': p['name'], 'nameEn': p['nameEn'],
                'category': p['category'], 'defaultMoq': p['defaultMoq'],
                'defaultMoqUnit': p['defaultMoqUnit'],
            })
            if s != 200:
                print(f'failed to create product {p["code"]}: {product}')
                sys.exit(1)
            product_id = product['id']
            created_products += 1
        for spec in p['specs']:
            dup = find('FusanheProductSpec', 'version', spec['version'])
            # version is unique per product; scope the check to this product's list
            s, listr = call('GET', f"/FusanheProductSpec?maxSize=50&where[0][type]=equals&where[0][attribute]=productId&where[0][value]={product_id}&where[1][type]=equals&where[1][attribute]=version&where[1][value]={spec['version']}")
            if s == 200 and listr.get('total'):
                continue
            payload = {k: v for k, v in spec.items() if k != 'approve'}
            payload['productId'] = product_id
            s, created = call('POST', '/FusanheProductSpec', payload)
            if s != 200:
                print(f'failed to create spec {spec["version"]} for {p["code"]}: {created}')
                sys.exit(1)
            created_specs += 1
            if spec.get('approve'):
                s, out = call('POST', f"/Fusanhe/product-spec/{created['id']}/approve")
                if s == 200:
                    approved += 1
    print(json.dumps({
        'createdProducts': created_products, 'createdSpecs': created_specs,
        'approvedSpecs': approved,
    }, ensure_ascii=False))


if __name__ == '__main__':
    main()
