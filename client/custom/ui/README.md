# Unified CRM Web 1.0.0

The single Web app is mounted by `client/custom/src/views/fusanhe/workspace.js`.
React 19 + TypeScript + Vite + Lucide; five workspace pages, existing Espo ACL/AJAX bridge.

```bash
npm ci
npm test
npm run build
npx vite --host 127.0.0.1 --port 5176
```

Open `http://127.0.0.1:5176/preview.html?preview=1` for synthetic local fixtures.
Standalone preview rejects all real backend requests. Tests may use `tests/capture.html`
to exercise failures/recovery without remounting. Browser checks run from the repository
root with `python3 tests/unified_ui_browser.py` and Python Playwright/Chromium or Chrome.

The production IIFE and CSS are committed in `../res/workspace` so an Espo deployment
can serve this version without Node. Rebuild both assets after every source change.

See `specs/005-unified-crm-web` and `docs/RELEASE_CRM_WEB_1.0.0.md` for the accepted design,
validation and provider/telemetry boundaries. Old HIG and crm-web source is preserved in
archive tags; it is not built or mounted alongside this app.
