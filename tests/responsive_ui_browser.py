"""Responsive acceptance against isolated preview and the native Espo login.

Start Vite on 5176, then run: python3 tests/responsive_ui_browser.py
The login check serves local UI assets over the live read-only login page.
Use --deployed after publishing to verify the actual deployed login assets.
No login submission, CRM mutation, or paid provider call is made.
"""
import argparse
import json
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'test-results' / 'responsive'
SIZES = {
    'phone-small': (320, 740),
    'phone': (390, 844),
    'phone-landscape': (844, 390),
    'ipad-portrait': (768, 1024),
    'ipad-landscape': (1180, 820),
    'laptop': (1366, 768),
    'desktop': (1920, 1080),
}
PAGES = ['home', 'messages', 'customers', 'ai', 'knowledge']


def overflow(page, selector):
    return page.locator(selector).evaluate(
        '(e) => ({width:e.clientWidth, scroll:e.scrollWidth})')


def run():
    parser = argparse.ArgumentParser()
    parser.add_argument('--deployed', action='store_true')
    parser.add_argument('--engines', default='chromium,webkit,firefox')
    parser.add_argument('--login-only', action='store_true')
    parser.add_argument('--sizes', default=','.join(SIZES))
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    results, failures = [], []
    with sync_playwright() as p:
        for engine in args.engines.split(','):
            browser = getattr(p, engine).launch(headless=True)
            for label in args.sizes.split(','):
                width, height = SIZES[label]
                context = browser.new_context(viewport={'width': width, 'height': height},
                                              reduced_motion='reduce', has_touch=width < 1280)
                page = context.new_page()
                errors = []
                page.on('pageerror', lambda e: errors.append(str(e)))
                try:
                    if not args.deployed:
                        for asset in ['res/fusanhe/brand.css', 'src/views/fusanhe/login.js']:
                            file = ROOT / 'client/custom' / asset
                            mime = 'text/css' if asset.endswith('.css') else 'application/javascript'
                            page.route('**/client/custom/' + asset + '*',
                                       lambda route, request, file=file, mime=mime: route.fulfill(
                                           path=str(file), content_type=mime))
                    page.goto('https://gzfusanhesp.com/', wait_until='networkidle')
                    expect(page.locator('#btn-login')).to_be_visible()
                    expect(page.locator('label[for="field-userName"]')).to_have_text('账号')
                    panel = page.locator('#login').bounding_box()
                    assert panel and panel['x'] >= -1 and panel['x'] + panel['width'] <= width + 1, panel
                    layout = page.locator('.fsh-login-layout').bounding_box()
                    content_width = page.evaluate('document.documentElement.clientWidth')
                    assert layout and abs(layout['x'] + layout['width'] / 2 - content_width / 2) <= 2, layout
                    dims = overflow(page, 'body')
                    assert dims['scroll'] <= width + 1, dims
                    page.locator('#field-password').fill('layout-only')
                    page.locator('[data-action="toggleShowPassword"]').click()
                    expect(page.locator('#field-password')).to_have_attribute('type', 'text')
                    page.locator('#field-password').fill('')
                    page.locator('#field-password').blur()
                    page.screenshot(path=str(OUT / f'{engine}-{label}-login.png'), full_page=True)
                    results.append(f'{engine}/{label}/login')
                    if not args.login_only:
                        page.unroute_all(behavior='wait')
                        page.route('**/client/custom/res/fusanhe/logo-full.png',
                                   lambda route: route.fulfill(path=str(ROOT / 'client/custom/res/fusanhe/logo-full.png'), content_type='image/png'))
                        for target in PAGES:
                            page.goto(f'http://127.0.0.1:5176/preview.html?preview=1&workspace={target}')
                            expect(page.locator('.w-main')).to_be_visible()
                            page.wait_for_timeout(250)
                            dims = overflow(page, '.w-main')
                            assert dims['scroll'] <= dims['width'] + 1, (target, dims)
                            page.screenshot(path=str(OUT / f'{engine}-{label}-{target}.png'))
                            results.append(f'{engine}/{label}/{target}')
                        if page.locator('.w-mobile-menu').is_visible():
                            page.locator('.w-mobile-menu').click()
                            expect(page.locator('.w-app')).to_have_class(__import__('re').compile('menu-open'))
                            page.keyboard.press('Escape')
                            expect(page.locator('.w-app')).not_to_have_class(__import__('re').compile('menu-open'))
                            page.locator('.w-mobile-menu').click()
                            page.get_by_role('button', name='客户与评级', exact=True).click()
                            expect(page.locator('.w-main h1')).to_have_text('客户与评级')
                        page.locator('.w-global-search').click()
                        expect(page.get_by_role('dialog')).to_be_visible()
                        box = page.get_by_role('dialog').bounding_box()
                        assert box and box['x'] >= -1 and box['x'] + box['width'] <= width + 1, box
                        page.keyboard.press('Escape')
                        expect(page.get_by_role('dialog')).to_have_count(0)
                        page.goto('http://127.0.0.1:5176/preview.html?preview=1&workspace=messages&record=v2')
                        expect(page.locator('.w-chat')).to_be_visible()
                        chat = page.locator('.w-chat').bounding_box()
                        assert chat and chat['width'] >= min(300, width - 28), chat
                        if width < 1400:
                            page.get_by_role('button', name='客户资料', exact=True).click()
                            expect(page.locator('.w-chat-inspector')).to_be_visible()
                            page.locator('.w-chat-inspector').get_by_role('button', name='收起', exact=True).click()
                            expect(page.locator('.w-chat-inspector')).not_to_be_visible()
                    assert not errors, errors
                    print(f'PASS {engine}/{label}', flush=True)
                except Exception as exc:
                    failures.append({'case': f'{engine}/{label}', 'error': str(exc)})
                    print(f'FAIL {engine}/{label}: {exc}', flush=True)
                    page.screenshot(path=str(OUT / f'{engine}-{label}-failure.png'), full_page=True)
                finally:
                    context.close()
            browser.close()
    (OUT / ('results-' + args.engines.replace(',', '-') + '.json')).write_text(json.dumps({'passed': results, 'failures': failures}, ensure_ascii=False, indent=2))
    print(json.dumps({'passed': len(results), 'failures': failures}, ensure_ascii=False, indent=2))
    if failures:
        raise SystemExit(1)


if __name__ == '__main__':
    run()
