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
Independent acceptance found and resolved generic private-entity reads, missing active background scheduling, unavailable-default model gating, misleading terminal failure copy, and administrator recovery for non-admin owners. Eight isolated runtime acceptance tests, live-component desktop/mobile browser workflows and additional 23 regressions passed. See [acceptance.md](acceptance.md). Root separately verified actual built IIFE in the EspoCRM host with unavailable paid action disabled. A fresh independent acceptance agent reran all eight acceptance tests (19.282s), the media service contract and complete live-component browser regression after the privileged recovery update; no unresolved blockers.

## GitHub verification

Initial PR commit 17281b4 passed all three verify jobs in [run 36689623302](https://github.com/hanmin6/fsh/actions/runs/36689623302). Final code commit `631fb8f6b39bb9d7b7c1dd08938f47978f3b1b8a` passed all three jobs in [run 36691801760](https://github.com/hanmin6/fsh/actions/runs/36691801760): spec-python-php (including isolated dual-AI acceptance), frontend (including both browser suites and committed build consistency), and Android test/lint/assembly.

[PR #2](https://github.com/hanmin6/fsh/pull/2) merged into `main` at `095c9907966ec7d1e777889fe3724ed04a2d0bb7`. The subsequent release-record commit carries annotated tag `crm-web-v1.1.0`; it changes documentation only. The merged temporary remote branch is removed after the tag and main are verified on GitHub. Existing archive tags and unrelated branches remain intact. Per user instruction this release is GitHub-only; no server deployment occurred. Rollback instructions are in [release handoff](../../docs/RELEASE_CRM_WEB_1.1.0.md).

## Limits
Static image generation intentionally disabled per user. Real video smoke used text-only 480P; actual first-frame generation with a user-owned public image, customer data, production deployment and real capture platforms were not exercised. Local images are not automatically published and text planning does not inspect them. Monetary fees remain unknown; count/concurrency limits are enforced. Raw customer messages/internal knowledge are omitted from real text prompts, so full translation and fact-rich responses require later explicitly approved data policy.
