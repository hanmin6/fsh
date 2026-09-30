# CRM Web 1.1.0 verification

Date: 2026-09-30. All CRM runtime/browser fixtures fictional; production not deployed and customer messages not sent.

## Root verification
- Spec prerequisites passed for specs/006-dual-ai-gateways.
- make verify-offline: 45 Python tests and text_gateway_contract.php, media_gateway_contract.php, media_service_contract.php passed.
- Alibaba/MIC offline contracts: 39 discovered, 38 passed, 1 intentional live-connector skip.
- Existing isolated runtime: 39 passed (history, Alibaba synchronization, ratings, platform filtering, products, certificates, security). Initial standalone HistoryAiProvider require missed TextGateway; corrected test loader and full suite reran successfully.
- Frontend 12 domain tests + 13 native frontend tests passed; TypeScript and Vite production build passed, generated assets included.
- Existing synthetic browser desktop/mobile workflows passed. Initial browser invocation found Vite stopped; restarted loopback Vite and reran successfully.
- Isolated EspoCRM rebuild, custom status/job/asset APIs and media-reconcile command passed. Tests use no real relay keys.
- Real provider evidence: three selected text models each returned valid JSON; video produced/downloaded/playable 5-second synthetic MP4. See provider-evidence.md for precise protocols and limitations.
- Changed/untracked release files scanned for exact real credentials: no leaks. Private configuration is Git-ignored and chmod 600.

## Independent acceptance
Review underway. Found generic private-entity read bypass and missing active background schedule. Generic controllers now deny access; custom endpoints retain owner-only sanitized responses. Bootstrap now explicitly installs an active minute schedule on existing installations. Final independent recheck/report will follow before release.

## Limits
Static image generation intentionally disabled per user. Real video smoke used text-only 480P; actual first-frame generation with a user-owned public image, customer data, production deployment and real capture platforms were not exercised. Local images are not automatically published and text planning does not inspect them. Monetary fees remain unknown; count/concurrency limits are enforced. Raw customer messages/internal knowledge are omitted from real text prompts, so full translation and fact-rich responses require later explicitly approved data policy.
