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

Deployment target: the supplied SSH server, release path
`/home/fusanhe/fusanhe-crm/current`, commit `fad97fc`.

- Docker Compose `edge` profile started successfully with AMD64 images.
- MariaDB, EspoCRM, daemon and WebSocket report `healthy`; Caddy is listening on
  host ports 80/443. Internal CRM and WebSocket ports remain loopback-bound.
- EspoCRM `bin/command rebuild` completed successfully.
- Native administrator login against the server-local CRM endpoint returned HTTP
  200.
- The fixed `**workspace:public-workspace` marker returned HTTP 401 with the
  default environment.
- HTTP on the Caddy endpoint returned HTTP 308 to the HTTPS origin.
- A database dump was created under the server backup directory with mode 600.

Public HTTPS is not yet reachable through `gzfusanhesp.com`: the current public
DNS/edge still resolves to the independent-site endpoint (`187.52.122.192`),
whose response redirects to `fshfoodingredients.com`. Caddy's ACME challenge
therefore fails until DNS and the 80/443 forwarding for the CRM server are
changed. No independent-site DNS or application was modified by this deployment.

No independent-site DNS or application is part of this verification.
