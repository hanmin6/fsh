# Made-in-China Complete Conversation CRM Integration Implementation Plan

> **For agentic workers:** Execute the checked tasks in order with GPT-6 Luna (high). Use isolated checkouts for implementation; review each task's diff and evidence before starting its dependent task. Steps use `- [ ]` for tracking.

**Goal:** Import complete MIC inquiry and TradeMessenger history into CRM with Leads and deliver individually approved greetings through the MIC gateway with confirmed results.

**Architecture:** The existing MIC gateway owns authorized browser access, local source cache and Outbox. A new bridge in that repository reads its versioned API, keeps CRM import checkpoints, and acts as a CRM Agent for approved sends. CRM owns identities, Leads, conversations, messages, approval and audit. MIC and Alibaba remain separate channels.

**Tech Stack:** Python 3.11+, FastAPI, Playwright, SQLAlchemy/SQLite, pytest; EspoCRM 10.0.8, PHP 8.3, MariaDB, Docker Compose.

**Requirements:** [spec.md](../../../specs/003-made-in-china-crm-integration/spec.md) · [architecture plan](../../../specs/003-made-in-china-crm-integration/plan.md) · existing [Alibaba sync contract](2026-09-21-alibaba-message-sync-foundation.md).

---

## Confirmed behavior and delivery rules

- Import every accessible inquiry body and every later inbound and outbound chat bubble. A one-message inquiry import does not satisfy completion.
- A stable MIC `buyer_reference` creates or reuses one Lead; missing name uses `MIC 买家 <buyer_reference>` as an explicit temporary display name. Later source data may replace only that generated display name. Different buyer IDs never merge solely by name.
- Greetings are drafted and individually approved in CRM before an Agent can send them. Keep `FUSANHE_OUTBOUND_PAUSED=true` until the operator's designated live acceptance step.
- The bridge must never report success for a gateway job in `queued`, `sending`, `uncertain`, `requires_human_review`, or `failed`. An `uncertain` result waits for reconciliation and must not be submitted with a new idempotency key.
- The MIC gateway currently parses only initial inquiry bodies from `/message.do`; its operations manual records a TradeMessenger initialization error during discovery. This is the first technical gate. If the authenticated site still cannot yield chat history, keep MIC-01 and dependent live acceptance open and report the evidence. Saved DOM snapshots do not expose a durable chat message ID or a rendered conversation ID marker; live acceptance must establish reliable identity and idempotency before enabling real reads or sends.
- Do not copy real tokens, cookies, buyer names, messages, browser profiles, SQLite databases or unsanitized screenshots into Git or test fixtures.

## File map

`G:\FSH\made-in-china\made-in-china` (independent gateway repository):

- Modify `src/mic_gateway/adapters/made_in_china/selectors.py` and `adapter.py`: source list pagination, conversation metadata and complete chat extraction.
- Modify `src/mic_gateway/adapters/base.py`, `domain.py`, `sync/engine.py`, `db/models.py`, `db/repositories.py`, `api/schemas.py`, `api/routes_read.py` and add an Alembic revision only where the verified source contract needs new stable IDs, buyer metadata, source sequence or completeness state.
- Create `src/mic_gateway/crm_bridge/config.py`, `crm_client.py`, `importer.py`, `worker.py`, `state.py`, `cli.py`: a transport and checkpoint layer outside browser request handlers. Place state under `MIC_APP_DATA_DIR`.
- Extend `tests/contract/test_conversations_contract.py`, `test_messages_contract.py`, `tests/integration/test_sync_engine.py`, `test_read_api.py`, `test_outbox_worker.py`; create focused `tests/unit/test_crm_bridge_*.py` with fake gateway/CRM responses.
- Update `.env.example`, `README.md`, `docs/crm_integration_api.md`, `docs/operations.md`. Do not put the CRM Agent token in CLI arguments or committed files.

`G:\FSH\CRM\fsh` (CRM repository):

- Create `custom/Espo/Custom/Tools/Fusanhe/Api/PostMadeInChinaSync.php` and `custom/Espo/Custom/Tools/Fusanhe/MadeInChinaSyncService.php`; add `/Fusanhe/mic/sync` to `custom/Espo/Custom/Resources/routes.json` and `metadata/app/api.json` as required by EspoCRM routing.
- Modify `custom/Espo/Custom/Tools/Fusanhe/IdentityService.php` only for channel-neutral Lead description and safe temporary-name upgrading. Reuse `AutomationAuth`, `WorkflowService` and existing task APIs; change claim filtering only if tests show MIC Agent can receive another channel's task.
- Create `tests/test_mic_sync_contract.py`, `tests/test_mic_sync_runtime.py`, `tests/test_mic_outbound_runtime.py`; update `docs/API_AGENT_HANDOFF.md`, `docs/operations.md`, `docs/PROJECT_STATUS.md` after evidence exists.
- Keep `custom/Espo/Custom/Tools/Fusanhe/Connector/MadeInChinaConnector.php` as a placeholder unless the CRM connector interface is explicitly exercised by this flow; the bridge and Agent API are the integration boundary.

## Contract to freeze before implementation

CRM `POST /Fusanhe/mic/sync` uses MIC Agent authentication and an account-scoped batch:

```json
{
  "jobId": "mic-backfill-20260923-01",
  "requestId": "mic-backfill-20260923-01:source-123:1",
  "accountHandle": "mic-seller-01",
  "syncMode": "backfill",
  "batchNo": 1,
  "finalBatch": true,
  "conversation": {
    "sourceId": "source-123",
    "buyerExternalId": "buyer-456",
    "buyerName": "MIC 买家 buyer-456",
    "buyerNameIsPlaceholder": true,
    "subject": "Product inquiry",
    "country": "",
    "unreadCount": 0
  },
  "messages": [
    {
      "externalId": "source-123:inquiry",
      "sourceSequence": 1,
      "direction": "inbound",
      "messageType": "initialInquiry",
      "body": "Sanitized example inquiry",
      "sourceTimestampRaw": "2026-09-23T08:00:00Z",
      "timestampConfidence": "high"
    }
  ]
}
```

Use the real MIC source ID as the CRM conversation `externalId`; keep the gateway UUID in bridge state to call gateway endpoints. Return created/deduplicated counts and IDs in the CRM response. A repeated `requestId` with the same canonical payload returns the prior response; the same ID with different content returns conflict. The bridge advances its checkpoint only after a confirmed CRM response. Message IDs use durable platform IDs when present. If the source has no ID, use a deterministic fingerprint of the observed account, conversation, direction, normalized body, timestamp, sender and safe attachment metadata, with an occurrence ordinal only among indistinguishable observations. Do not include absolute visible sequence in the fingerprint: older history or reorder can change it. This fallback is best effort if the source later edits metadata or time formatting; cross-change idempotency must be demonstrated in live acceptance or the import remains gated. Never use a random ID for historical messages.

## Task 1: Verify the TradeMessenger source contract (MIC-01)

**Files:** `src/mic_gateway/adapters/made_in_china/{selectors.py,adapter.py}`; `tests/contract/fixtures/messages-page.sanitized.json`; `tests/contract/test_messages_contract.py`; `docs/operations.md`.

- [ ] Read the existing sanitized fixture and current parser; record exactly which fields represent inquiry, buyer, sender, time, message ID and attachments. Use `python -m pytest tests/contract/test_messages_contract.py tests/unit/test_made_in_china_adapter.py -q` as the baseline.
- [ ] In the authorized, headed MIC session use the gateway's read-only `discover --resource messages` flow to identify TradeMessenger history requests or DOM bubbles, older-history pagination and buyer metadata. Sanitize captures before adding fixtures. Never trigger a send during discovery.
- [ ] Add a sanitized fixture containing inquiry, later inbound and later outbound chat plus two pages of history. Add a contract test that expects all three messages in source order and a stable buyer reference. Confirm that it fails against the current inquiry-only parser.
- [ ] Record the validated selector/request path and any site limitation in `docs/operations.md`. If the chat component still fails initialization, stop source parsing work here and report the exact non-secret error; do not fabricate history or mark this task complete.

## Task 2: Complete gateway ingestion and read API (MIC-01, MIC-02)

**Files:** `src/mic_gateway/adapters/made_in_china/{selectors.py,adapter.py}`, `adapters/base.py`, `domain.py`, `sync/engine.py`, `db/{models.py,repositories.py}`, `api/{schemas.py,routes_read.py}` and a database migration if columns change; tests named in the file map.

- [ ] Add failing tests for: every source list page being visited; older chat pages merged without duplication; stable source IDs; inquiry first, then chat in absolute source order; both directions; buyer details; unread/source timestamps; an incomplete page raising a source-contract error. Run `python -m pytest tests/contract tests/integration/test_sync_engine.py tests/integration/test_read_api.py -q` and capture the failures.
- [ ] Implement pagination using the site's verified cursor/page mechanism; do not discard the `SourceCheckpoint` argument. Persist a page cursor or overlap watermark only after that page's records commit. Keep a per-conversation completeness marker so API consumers cannot mistake an initial inquiry for complete history.
- [ ] Parse the verified TradeMessenger response or DOM into normalized `SourceMessage` objects. Preserve message source ID when present; for missing IDs use the deterministic fingerprint defined above. Store source sequence, raw source timestamp and direction; make `GET /v1/conversations/{id}/messages` return them without breaking existing fields.
- [ ] Migrate existing SQLite rows without deleting inquiry or Outbox records. Backfill sequence and completeness only when evidence allows it; otherwise expose `history_complete=false` until reread. Run the focused tests and `python -m pytest tests -q` with live tests disabled.

## Task 3: CRM MIC import endpoint and Lead behavior (MIC-02, MIC-03)

**Files:** `custom/Espo/Custom/Tools/Fusanhe/{Api/PostMadeInChinaSync.php,MadeInChinaSyncService.php,IdentityService.php}`; `custom/Espo/Custom/Resources/{routes.json,metadata/app/api.json}`; `tests/{test_mic_sync_contract.py,test_mic_sync_runtime.py}`.

- [ ] Add offline contract tests for the route, `MadeInChina` Agent capability, batch limits, account/source identifiers, canonical replay conflict and forbidden source fields. Add isolated CRM runtime tests with two inquiries from one buyer and a same-name different buyer; verify one Lead for the first ID and a separate Lead for the second.
- [ ] Implement the endpoint with `AutomationAuth::assertAgent` and explicit `MadeInChina` capability validation. In one transaction, upsert the account-scoped channel, conversation, identity, Lead and messages; use unique source IDs plus content hashes for replay protection. Reuse existing identity matching rules; never merge on name alone.
- [ ] Keep historical mode free of draft creation, task creation and unread changes. Mark `backfillCompletedAt` only on a complete final batch. Upgrade only generated placeholder Lead names when a real source name arrives; do not overwrite human-edited CRM fields. Keep audit payloads minimal and redact message bodies.
- [ ] Run `python -m pytest tests/test_mic_sync_contract.py -q`, then the isolated `tests/test_mic_sync_runtime.py`; lint the changed PHP files with `php -l` in the project container if host PHP is absent. Run the existing Alibaba sync regression tests to show compatibility.

## Task 4: MIC-to-CRM bridge and operator CLI (MIC-02, MIC-05)

**Files:** new `src/mic_gateway/crm_bridge/{config.py,crm_client.py,importer.py,state.py,cli.py}`; `.env.example`; `tests/unit/test_crm_bridge_*.py`; `README.md`.

- [ ] Add tests for CLI `register`, `backfill`, `once`, `daemon`, `status`; CRM URL restricted to loopback by default and remote HTTPS only with an explicit flag; separate MIC read and CRM Agent credentials; 401 stop, 429/5xx bounded retry, checkpoint after confirmed response, interrupted-page resume, repeated backfill, and incomplete-history refusal.
- [ ] Implement the bridge using the gateway's `crm_read` API and a local SQLite checkpoint in `MIC_APP_DATA_DIR`. Paginate conversations and each message history fully. Normalize the frozen CRM contract, batch at most 100 messages, and push with stable `jobId`/`requestId`. Create or rotate the CRM Agent with capability `MadeInChina`; print the new token once and do not store it.
- [ ] `backfill` walks all accessible conversations; `once` processes source updates; `daemon` repeats `once` on a configurable interval; `status` reports non-secret progress and failures. Source messages already sent by gateway must import as outbound history without creating a new CRM send task.
- [ ] Run `python -m pytest tests/unit/test_crm_bridge_*.py tests/integration/test_read_api.py -q`; document exact CLI usage, configuration, restart and credential rotation. Confirm `.gitignore` excludes bridge state, profiles and logs.

## Task 5: Approved outbound Agent and two-state reconciliation (MIC-04)

**Files:** new `src/mic_gateway/crm_bridge/worker.py`; `crm_client.py`, `state.py`, `cli.py`; `tests/unit/test_crm_bridge_worker.py`; CRM `tests/test_mic_outbound_runtime.py`.

- [ ] Add tests showing an Agent with `MadeInChina` capability cannot claim Alibaba tasks; paused CRM returns no task; only an approved, real MIC task gets submitted to the MIC gateway; `mock` never invokes the browser; duplicate polls reuse the same gateway idempotency key.
- [ ] Register a dedicated MIC Agent and report heartbeat based on gateway `/v1/status`. On claim, verify `channelType=MadeInChina`, target source ID and task body, then mark CRM task sending. Resolve the gateway conversation UUID from the MIC source ID. Submit `POST /v1/conversations/{uuid}/messages` with `intent=greeting` and idempotency key derived from the CRM task ID; persist the returned gateway job ID before polling.
- [ ] Poll `/v1/jobs/{jobId}`. Report CRM success only for `sent` with a confirmed source message ID; map `failed` to a safe failure code. For `uncertain`, `queued`, `sending` or `requires_human_review`, retain the same job/key, expose action required, and do not report success or resubmit. Add a recovery path after worker restart that resumes each persisted gateway job before claiming another task.
- [ ] Test global pause immediately before gateway submission as well as at CRM claim. If pause state cannot be established, fail closed. Verify human takeover and expired/cancelled tasks through CRM runtime tests. Run `python -m pytest tests/unit/test_crm_bridge_worker.py tests/integration/test_outbox_worker.py -q` and the CRM outbound runtime test.

## Task 6: Cross-system verification and handoff (MIC-01–MIC-05)

**Files:** `G:\FSH\CRM\fsh\docs/{API_AGENT_HANDOFF.md,operations.md,PROJECT_STATUS.md}`, MIC `docs/{crm_integration_api.md,operations.md}`, and `specs/003-made-in-china-crm-integration/{tasks.md,verification.md}`.

- [ ] Run MIC offline suite, CRM `make spec-check`, `make verify-offline`, PHP lint, and the isolated CRM runtime suite. Also run `SPECIFY_FEATURE_DIRECTORY=specs/003-made-in-china-crm-integration ./.specify/scripts/bash/check-prerequisites.sh --json --require-spec --require-tasks --include-tasks` in a Bash environment to check this feature, because the current `Makefile` pins `spec-check` to 002. Record commands, counts and skipped tests in `verification.md`. Do not treat existing 2026-09-21 test counts as new evidence.
- [ ] In a disposable CRM stack with sanitized gateway fixtures, verify full backfill, restart/resume, two-buyer identity separation, new inbound increment, outbound history import, approval, pause, failure and uncertain-job recovery. Capture counts/IDs without private message content.
- [ ] In the authorized MIC account, perform read-only acceptance first: compare a selected conversation's inquiry and full bilateral history with CRM, including older pages. Only after the operator identifies a specific approved test conversation and unpauses the test stack, execute one greeting and verify the platform bubble, gateway job and CRM receipt. Restore pause immediately afterward. If the site login or chat component is unavailable, record this as an unmet live gate.
- [ ] Update the two repositories' operations docs, health checks, secrets setup and recovery instructions. Mark individual tasks complete only with evidence. Leave production rollout pending until live validation and deployment configuration are separately reviewed.

## Review and rollback checkpoints

1. Task 1's live history proof is the gate for claiming MIC-01 complete and for live rollout. Offline parser, CRM contract and bridge work may proceed from evidenced structures and synthetic fixtures while this gate is open; tests must not assert unobserved site behavior as verified.
2. After Tasks 2–4, review source contract, CRM replay/Lead behavior and Alibaba regressions before activating any worker.
3. After Task 5, review the state mapping across CRM `pending/claimed/sending/sent/failed` and gateway `queued/sending/sent/failed/uncertain` before a live send.
4. Rollback: stop MIC bridge and worker, revoke their CRM Agent credential and MIC API keys, keep CRM global pause on, and retain imported data and audit records. Revert code by repository revision; do not erase messages or Leads as part of rollback.

## Agent handoff

The user requested GPT-6 Luna at high reasoning for subsequent implementation. Dispatch one bounded task at a time, beginning with Task 1, passing this plan and both repository paths. Review source evidence before dispatching dependent tasks. The MIC repository lies outside the current writable workspace, so implementation there requires a writable checkout or filesystem approval; do not silently replace it with a different source tree.
