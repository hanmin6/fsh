# Independent acceptance — CRM Web 1.1.0

Date: 2026-09-30. Reviewer: independent acceptance agent, separate from the text/media implementers.

Final focused review: a separate independent reviewer checked the privileged-recovery specification against the current service, strengthened the eighth runtime case with a persisted private plan/brief, and reran all eight isolated runtime cases (**8 passed in 19.282s**), `media_service_contract.php` (**passed**) and the complete `dual_ai_browser.py` regression (**passed**). The other evidence below was produced by the prior independent acceptance pass; it was not rerun in this final focused review.

Verdict: **PASS for the specified isolated integration scope. No unresolved release blockers found.** This is not a production deployment or a production-customer acceptance claim. No paid generation calls were made by this reviewer, and no real credentials or locally stored gateway configuration were read.

## Findings resolved before acceptance

1. **Owner privacy bypass through generic CRM reads.** Initially, a regular role with `MediaAsset.read=all` could retrieve another owner's source record and its private file key using generic list/detail APIs, while the dedicated content endpoint correctly returned 404. All three internal creative controllers now reject generic access; export/global search are disabled. Independent runtime tests cover list/detail/create/update/delete for both regular users and administrators. Dedicated responses remain owner-scoped and sanitized.
2. **Background reconciliation was not registered.** The isolated database initially had no `FusanheMediaReconcile` scheduled record. Metadata plus idempotent bootstrap now register one Active job, scheduled every minute. The real scheduled-job class archives a fake-provider result without a browser. The real CLI also executes successfully against the isolated CRM (`media_jobs_checked=2`); its configured channels are disabled and it makes no paid submissions.
3. **Unavailable default blocked explicit model selection.** The creative UI initially kept recommendation disabled even after selecting an available Grok model when the default GPT model was unavailable. It now checks the explicitly selected model. The browser regression confirms the unavailable default is retained until the user chooses Grok, with returned provenance `grok-4.7`.
4. **Terminal failure copy implied ongoing processing.** Failed tasks now say processing has stopped and that failure/charges need review. Browser verification confirms terminal failure does not display the active-background message.
5. **Regular owners' uncertain submissions were unrecoverable.** Root identified that recovery required both ownership and administrator status. The specification now permits a narrow administrator operation on another owner's uncertain video job. Independent runtime verification confirms the regular owner receives 403; administrator recovery succeeds with only `requestId/id/status`; owner, source, plan and private brief remain unchanged; the administrator is audited as a user actor; the owner can subsequently read its selected private concept and reconcile the task; administrator private job reads, reconciliation and source download still return 404; generic plan access remains denied and the job/brief are excluded from administrator job lists; and another task cannot claim the same provider ID (409), leaving that second task uncertain and without a remote ID. This operation restores an existing task ID without submitting a paid generation request. Fake-service contracts independently verify cross-owner recovery never calls submit or poll.

## Evidence and coverage

| Evidence | Result | Scope |
|---|---|---|
| `tests/test_dual_ai_acceptance.py` | 8 passed | Isolated EspoCRM/MariaDB on loopback port 18082; fictional users, records and injected transports |
| `tests/text_gateway_contract.php` | Passed | GPT Responses versus Grok/Gemini Chat Completions, exact returned model, no substitutions/retries/mock fallback, isolated keys, bounded/error-sanitized output, reply/history anonymization |
| `tests/media_gateway_contract.php` | Passed | MiniMax V2 request/state contracts, first-frame ratio omission, disabled static image generation, key separation, URL/SSRF boundary, no automatic retry |
| `tests/media_service_contract.php` | Passed | Real service with fake persistence/transport; transaction failure, result deduplication, uncertain submission, ownership and budgets |
| `tests/dual_ai_browser.py` | Passed | Actual live React component through a fictional isolated HostBridge; no CRM/provider transport |
| `tests/unified_ui_browser.py` | Passed | Existing capture, human approval, takeover, handoff, rating and mobile regression |
| History/security/metadata/API Python regressions | 23 passed | `test_boss_insights`, `test_security_regression`, `test_contracts`, `test_api_contract` on the isolated stack where required |
| Frontend tests/build | 12 passed; TypeScript/Vite build passed | Current source, including the model-selection correction |

The independent persisted-service test verifies one text call for replayed planning; one paid POST for a replayed media request; conflict on changed payload with the same key; explicit source-transfer consent; no static image submission; background completion; private archived bytes; owner denial including administrators; completed-result replay; uncertain timeout without resubmission; manual recovery that only queries; first-frame requests without ratio; daily and active request caps that stop upstream submission; and conservative rejection of local/non-HTTPS/credential/fragment/alternate-port URLs. The fake-network query does not archive unrelated test jobs.

Server checks also verify unauthenticated 401, deny-all role 403 on custom routes, inaccessible associated Account 403, cross-owner 404, source-upload deduplication scoped to owner, no private storage key/hash in sanitized responses, and an Active every-minute scheduled record. Administrator recovery is the explicitly documented narrow mutation exception; it grants no private read access. Existing security regressions protect human approval and workflow state authority. Creative generation does not enqueue customer sending.

Browser checks verify upload/brief gating, unavailable choices, consent reset when a public URL changes, stale-plan gating after preferences change, persistent task history after refresh, reuse of the same plan/job request keys after refresh, selected-model provenance, private download links, terminal/uncertain/status-error honesty, and no horizontal overflow at 1440px and 390px. No uncaught JavaScript errors occurred. Desktop and mobile screenshots were visually inspected; panels, plan cards, forms, task states and download dialog remain readable and operable. The incumbent CRM visual system is preserved.

Screenshots are local fictional evidence under `test-results/dual-ai/`: `creative-desktop-plans.png`, `creative-mobile-input.png`, `creative-mobile-plans.png`, `creative-mobile-tasks.png`, `creative-mobile-download.png`, `creative-desktop-assets.png`, `creative-desktop-failed.png`, `creative-desktop-uncertain.png`, `creative-desktop-status-error.png`, `creative-mobile-status-error.png`, and `creative-mobile-explicit-model.png`.

## Reproduction

Start/bootstrap the dedicated isolated stack using `tests/unified-ui-compose.yaml` and fictional `.env.test` credentials, with port 18082. Never use production configuration. For the runtime acceptance suite:

```bash
RUN_DUAL_AI_ACCEPTANCE=1 \
ESPOCRM_API_URL=http://localhost:18082/api/v1 \
ESPOCRM_ADMIN_USERNAME=admin \
ESPOCRM_ADMIN_PASSWORD=<fictional-test-password> \
python3 -m unittest tests.test_dual_ai_acceptance -v
```

Run Vite on loopback port 5176, then `python3 tests/dual_ai_browser.py` and `python3 tests/unified_ui_browser.py`. PHP contracts run using `php:8.3-cli` with the repository mounted at `/app`. Regression suites that invoke Compose must set `COMPOSE_PROJECT_NAME=fusanhe-ui-v1-test`, `COMPOSE_FILE=tests/unified-ui-compose.yaml`, `COMPOSE_ENV_FILES=.env.test`, and the same isolated API/password settings. An initial regression invocation without those settings failed against unavailable default targets; the correctly scoped rerun passed all 23 checks.

## Explicit limits

- Provider catalog and real text/video protocol evidence is recorded separately in `provider-evidence.md`; it was reviewed, not repeated. The browser fixture MP4 is synthetic signature data used to check UI/download plumbing, not a playable-video claim. The root integrator separately decoded the already downloaded real synthetic video, reporting 832×480, 5.184 seconds and no browser decode error.
- Actual public first-frame generation was not charged or tested in this acceptance. Payload shape, transfer consent, URL validation and ratio omission are covered with fakes. Static image generation remains deliberately disabled.
- Request-count budgets are enforced; monetary cost remains unknown. Provider status surfaces report configuration and `healthChecked=false`, not a live-health claim.
- Production must keep the daemon running and execute rebuild/bootstrap with its complete server-only environment. Stored tasks/assets are retained on rollback. Provider tasks whose submission result is ambiguous need administrator verification; they are never blindly resubmitted.
- Browser evidence uses Chromium/Chrome with emulated viewport sizes. Physical touch devices, screen-reader operation, a complete WCAG audit, provider uptime and production/customer workflows were not exercised. The optional impeccable context launcher was unavailable; no `PRODUCT.md` or `DESIGN.md` existed, so the UI review used incumbent source and current screenshots directly.
