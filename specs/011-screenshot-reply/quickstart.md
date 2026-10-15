# Validation
Run `make spec-check SPECIFY_FEATURE_DIRECTORY=specs/011-screenshot-reply`, `make verify-offline`, `cd client/custom/ui && npm test && npm run build`, and `python3 -m unittest tests.test_reply_assistant`. PHP tests require PHP 8 with curl, mbstring and image metadata functions (`php tests/php/reply_assistant.php`).
Browser: use synthetic chat screenshot at 1440x1000 and 390x844, upload/paste/drop -> analyze -> select direction + custom -> generate -> edit/copy/refine -> modify direction. Test custom-only, image deletion, invalid files, unavailable AI and model error. Preview mode must explain no real screenshot analysis.
Live model acceptance requires environment-configured visual model. Do not commit screenshots containing actual customer data or secrets. Deploy only through existing deployment procedures then rebuild cache.

## Browser and preview
`cd client/custom/ui && npm ci && npm run build && npm run test:browser` uses installed Chrome by default (BROWSER_CHANNEL can select another installed Playwright channel). `npm run preview:reply` serves the fixed synthetic preview only, on loopback port 4175.

## Isolated HTTP acceptance
Use `tests/phase1-compose.yaml` with `.env.test.example` and a disposable override that changes the published port to 127.0.0.1:18088 and BOTH named volumes (the base file uses explicit volume names). Rebuild EspoCRM, then run `RUN_REPLY_RUNTIME=1 python3 -m unittest tests.test_reply_assistant_runtime -v`. Do not point it at production. The test provider is deliberately unconfigured. Remove only the stack/volumes created for this run after validation.

## Opt-in real provider smoke
With FUSANHE_TEXT_API_KEY / FUSANHE_TEXT_API_BASE_URL supplied securely (the model is fixed to gpt-6.1-sol) and the browser test's synthetic-chat.png present, run `FUSANHE_TEST_LIVE_AI=1 php tests/php/reply_assistant_live.php`. This performs two billable requests; it does not use real customer screenshots or print provider content.
