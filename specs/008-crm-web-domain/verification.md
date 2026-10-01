# CRM Web Domain verification

Date: 2026-10-02.

## Offline checks

- `python3 -m unittest tests.test_crm_web_domain tests.test_muse_crm_contract`: passed (9 tests).
- `python3 -m json.tool custom/Espo/Custom/Resources/metadata/authenticationMethods/FusanheWorkspace.json`:
  passed.
- `docker compose config --quiet`: passed. The local shell emitted warnings for intentionally
  unset secrets; no secret values are committed.
- `node --check client/custom/src/views/fusanhe/login.js`: passed.
- `npm test --prefix client/custom/ui`: passed (12 tests).
- `npm run build --prefix client/custom/ui`: passed (Vite production build).
- `node --test client/custom/tests/frontend.test.cjs`: passed (13 tests).
- `git diff --check`: passed.

## Runtime checks

Pending a target-server deployment. The runtime check must verify native
employee login, HTTP-to-HTTPS redirect, WebSocket upgrade, database isolation,
health checks after restart, and that the legacy public workspace marker is
rejected with the default environment.

The target server has not been deployed in this change. A successful local
configuration check is not evidence that `gzfusanhesp.com` is live. HTTP/HTTPS,
WebSocket, DNS, backup restore and native employee login still require the
separate server deployment acceptance run.

No independent-site DNS or application is part of this verification.
