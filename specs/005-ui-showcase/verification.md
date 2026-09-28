# Verification — 2026-09-28

- `node --check ui-showcase/fixtures.js` and `node --check ui-showcase/showcase.js` passed.
- `make spec-check SPECIFY_FEATURE_DIRECTORY=specs/005-ui-showcase` passed.
- Local static server returned HTTP 200 for `ui-showcase/` and the original generated UI runtime.
- Browser opened all 19 showcase navigation entries: four workbench/insights views, five queues, seven detail variants, and three catalog views. No blank or component error screen appeared. Home, conversation and insights were visually inspected.
- The showcase HostBridge only allows read permissions; `post` and `patch` reject, and outbound state is fixed to paused. All fixture contacts use fictional `.example` domains.
- CRM Docker was unavailable. Native EspoCRM forms and Android Compose screens were inventoried rather than represented as exact browser renders. Real CRM data, login, production actions, Android emulator and full visual acceptance remain outside this showcase verification.
