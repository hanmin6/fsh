# Made-in-China Automation Gateway Design

**Date:** 2026-09-19  
**Status:** Ready for user review  
**Scope:** One Made-in-China seller account on one always-on Windows computer

## 1. Purpose

Build a local automation gateway that gives an existing CRM read access to Made-in-China orders and inquiry conversations, and gives approved agents a controlled way to send low-risk conversational messages.

The service owns browser automation, synchronization, normalization, policy enforcement, and audit history. The CRM remains a separate system and is not modified by this project.

Success means:

- the CRM can query normalized orders, conversations, and messages through HTTP/JSON;
- agents can submit greetings, acknowledgements, holiday wishes, and non-commercial follow-ups for automatic delivery;
- messages involving quotations or commercial commitments are never automatically sent;
- repeated synchronization and repeated API requests do not create duplicate data or duplicate outbound messages;
- login loss, verification challenges, page changes, stalled synchronization, and uncertain sends are visible through service status;
- a new inquiry or message normally becomes queryable within 60 seconds.

## 2. Constraints and Assumptions

- Made-in-China does not provide an official API for this account.
- Automation is limited to the operator's authorized seller account and ordinary capabilities available in the logged-in web interface.
- The implementation will not bypass CAPTCHAs, verification challenges, access controls, or platform risk controls.
- One dedicated Windows user session stays logged in, and the browser remains available for manual intervention.
- The CRM and the gateway initially run on the same Windows computer.
- The gateway listens on `0.0.0.0` for future LAN or remote integration, while authentication and firewall restrictions are mandatory from the first release.
- The gateway does not generate campaign content or decide which customers should receive holiday greetings. The calling CRM or agent decides when and what to send; the gateway validates, queues, delivers, confirms, and audits the request.

## 3. Non-Goals for the First Release

- Multiple Made-in-China accounts or multiple tenants.
- Changes to the existing CRM.
- A custom web user interface.
- Arbitrary browser-control endpoints for agents.
- Automatic quotations, discounts, payment terms, stock promises, delivery commitments, contracts, or refunds.
- Webhooks, Redis, Celery, Kafka, or another external queue.
- Defeating platform verification or anti-automation controls.

## 4. Recommended Approach

Use a hybrid site adapter:

1. Playwright launches a persistent Chromium profile and establishes the authorized seller session.
2. Read operations prefer the same JSON/XHR requests used by the logged-in site when those requests can be identified and called reliably within the browser session.
3. When a read operation has no reliable request-level adapter, a DOM adapter extracts the required data from the rendered page.
4. Outbound messages initially use the visible website flow through Playwright and are confirmed by reading the resulting conversation state.
5. If an adapter detects an incompatible response or page structure, it fails closed and reports a site-contract error instead of guessing.

This approach is more maintainable than pure DOM scraping and less fragile than depending entirely on undocumented request formats. Every Made-in-China-specific operation remains behind a stable internal adapter interface so the public API does not change when the site adapter changes.

## 5. System Architecture

### 5.1 FastAPI service

The FastAPI application exposes versioned HTTP/JSON endpoints, validates API keys and roles, reads synchronized data from SQLite, and submits write operations to the persistent outbox. It does not directly drive a page from request handlers.

The default bind address is `0.0.0.0`; the port is configurable and defaults to `8787`. OpenAPI documentation is generated from the same request and response models used by the service.

### 5.2 Browser worker

A single browser worker owns one persistent Playwright browser context. All navigation and website mutation operations are serialized through this worker. API reads use SQLite and therefore do not compete for the browser.

The browser uses a dedicated profile directory owned by the dedicated Windows user. It does not reuse a personal Chrome profile. Authentication cookies and storage state never appear in API responses, application logs, or the Git repository.

### 5.3 Made-in-China site adapter

The adapter exposes internal operations for:

- listing and reading orders;
- listing conversations and inquiries;
- reading messages for a conversation;
- sending one message;
- checking authentication and site-contract health.

Each operation may have a request-level implementation and a DOM fallback. Callers do not know which implementation is active. Fallback is permitted only when the returned object can be validated against the normalized schema.

### 5.4 Synchronization scheduler

The scheduler runs independently from HTTP request handling:

- conversations and messages: every 30 seconds;
- orders: every 5 minutes;
- outbox: continuously, with one send in flight at a time.

The intervals are configuration values. Repeated failures use exponential backoff with a maximum delay. A successful run resets the backoff.

The adapter uses a stable website cursor or update timestamp when available. Otherwise, it rereads an overlapping recent window and de-duplicates by source identifiers and content fingerprints.

### 5.5 SQLite persistence

SQLite stores normalized records, source identifiers, source update times, safe raw response snapshots, synchronization checkpoints, outbox jobs, and audit events. Safe raw snapshots exclude cookies, authorization headers, session tokens, and other authentication material.

SQLite is the gateway's cache and operational database, not the CRM database. The CRM remains responsible for any data it imports.

### 5.6 Message policy and outbox

Agents never receive direct browser access. A send request first passes authentication, intent validation, content policy, conversation existence checks, and idempotency checks. Accepted requests are committed to the outbox before the API responds.

The browser worker sends one queued message, then rereads the conversation to verify that the expected message appears. If it cannot distinguish between a failed send and an unconfirmed successful send, it marks the job `uncertain` and performs reconciliation before any further attempt.

### 5.7 Health monitor

Health state covers process liveness, database readiness, browser availability, login state, last successful synchronization, outbox progress, verification challenges, and adapter contract failures.

Conditions requiring a person use the state `operator_action_required`. Synchronization or sending affected by that condition pauses until the operator resolves it and the health check succeeds.

## 6. Public API

All `/v1/*` endpoints require `X-API-Key`. Keys are assigned one of three roles:

- `crm_read`: read orders, conversations, messages, jobs, and status;
- `agent_send`: the read permissions plus submission of policy-eligible messages;
- `admin`: all permissions plus manual synchronization and operational actions.

### 6.1 Read endpoints

- `GET /v1/orders`
  - Filters: `updated_after`, `status`, `buyer`, and opaque `cursor`.
  - Returns a deterministic page and `next_cursor`.
- `GET /v1/orders/{order_id}`
  - Returns a normalized order and its source update time.
- `GET /v1/conversations`
  - Filters: `updated_after`, `unread`, `buyer`, and opaque `cursor`.
- `GET /v1/conversations/{conversation_id}/messages`
  - Returns messages in ascending source-time order with stable IDs.
- `GET /v1/jobs/{job_id}`
  - Returns the current state and a safe failure reason.
- `GET /v1/status`
  - Returns login, synchronization, adapter, browser, and outbox status without secrets.

### 6.2 Write endpoints

- `POST /v1/conversations/{conversation_id}/messages`
  - Requires `idempotency_key`, `intent`, `content`, and an optional caller reference.
  - Returns the same job for repeated requests with the same key and equivalent payload.
  - Rejects reuse of a key with a different payload.
- `POST /v1/admin/sync`
  - Queues a manual synchronization for one supported resource or all resources.
  - Does not run browser work inside the HTTP request.

### 6.3 Health endpoints

- `GET /health/live`: process liveness only.
- `GET /health/ready`: database, browser worker, and configuration readiness.

The health endpoints expose no customer or authentication data.

### 6.4 Response and error conventions

API responses use UTC ISO 8601 timestamps and stable source IDs. Collection endpoints use opaque cursor pagination rather than page numbers. Errors include a stable machine-readable code, a safe human-readable message, and a request ID.

Representative send states are:

- `queued`;
- `sending`;
- `sent`;
- `requires_human_review`;
- `failed`;
- `uncertain`.

## 7. Normalized Data Model

### 7.1 Order

An order includes the gateway ID, Made-in-China source ID, status, buyer reference, currency, totals as supplied by the source, source creation/update times, synchronization time, normalized line items, and a safe raw snapshot.

The gateway does not calculate new prices or infer commercial terms that are absent from the source.

### 7.2 Conversation

A conversation includes the gateway ID, source ID, buyer reference, inquiry subject, unread state, last-message time, source update time, and synchronization time.

### 7.3 Message

A message includes the gateway ID, source ID when available, conversation ID, direction, sender label, text content, attachment metadata without automatically downloading files, source time, synchronization time, and outbound job linkage when applicable.

### 7.4 Synchronization checkpoint

A checkpoint records the resource, source cursor or last update time, overlap window, last attempt, last success, failure count, and last safe error code.

### 7.5 Outbox job and audit event

An outbox job records the idempotency key, caller role/reference, conversation, declared intent, payload digest, state, attempt count, timestamps, and safe result metadata. Audit events record every policy decision and state transition without storing credentials.

## 8. Automatic Message Policy

Automatic sending is an explicit allowlist. Accepted intents are:

- `greeting`;
- `acknowledgement`;
- `holiday_wish`;
- `non_commercial_followup`.

The declared intent is necessary but not sufficient. A deterministic second-stage content gate checks for commercial or legally significant content, including:

- prices, quotations, discounts, or currency amounts;
- payment methods or payment terms;
- delivery dates, lead times, or shipping commitments;
- stock or production-capacity promises;
- contracts, warranties, refunds, or disputes.

If either the intent is not allowlisted or the content gate detects risk, the service does not enqueue a browser send. It records the decision and returns `requires_human_review`.

The gateway does not trust an agent-provided risk classification. Policy rules are configuration-controlled, versioned, and covered by regression tests. Policy failure is fail-closed: unavailable or invalid policy configuration blocks automatic sending.

## 9. Operational Model on Windows

Run the application and browser under a dedicated local Windows account using Task Scheduler with an `At log on` trigger. This keeps the browser in an interactive desktop session so a person can resolve authentication or verification issues.

Operational files are stored outside the source tree in a configurable application-data directory:

- Chromium profile;
- SQLite database;
- rotating logs;
- screenshots and Playwright traces captured on failure.

Windows ACLs restrict this directory to the dedicated account and administrators. Diagnostic artifacts use retention limits and are excluded from Git.

Although the API binds to `0.0.0.0`, Windows Firewall initially permits only localhost and explicitly trusted LAN addresses. Remote use requires a protected network path such as a VPN or a TLS reverse proxy; the FastAPI development server is not exposed directly to the public internet.

## 10. Failure Handling

- **Login expired:** pause affected jobs and set `operator_action_required`.
- **CAPTCHA or verification challenge:** pause; never attempt automated bypass.
- **Site contract changed:** stop the affected adapter operation, save redacted diagnostics, and expose a distinct contract-error code.
- **Transient navigation/network error:** retry with bounded exponential backoff.
- **Database busy or unavailable:** readiness fails and new writes are rejected safely.
- **Confirmed send failure:** retry only when the failure class is explicitly retryable.
- **Uncertain send:** reconcile by rereading the conversation; never blindly resend.
- **Process restart:** resume synchronization from checkpoints and resume only safe queued outbox jobs.
- **Stalled synchronization:** status becomes degraded when the configured freshness limit is exceeded.

## 11. Security and Privacy

- Store API keys as salted hashes; show plaintext only at provisioning time.
- Use constant-time key comparison and role-based authorization.
- Reject missing, invalid, revoked, or underprivileged keys before accessing business data.
- Never provide an endpoint for arbitrary navigation, selector execution, JavaScript evaluation, cookie access, or raw browser commands.
- Redact cookies, headers, tokens, email addresses, phone numbers, and full message bodies from routine logs.
- Do not commit `.env` files, browser profiles, databases, diagnostics, or customer data.
- Rotate logs and diagnostic artifacts with configurable retention.
- Apply request-size limits and rate limits, especially to send and admin endpoints.
- Record request IDs, caller identity, policy result, and job transitions for auditability.

## 12. Testing Strategy

### 12.1 Unit tests

Cover API authorization, request validation, cursor behavior, normalization, idempotency, state transitions, and message-policy allow/block cases.

### 12.2 Adapter contract tests

Use sanitized HTML fragments and JSON fixtures captured from authorized sessions. Contract tests assert required fields, stable identifiers, pagination behavior, and clear failure on incompatible structures.

### 12.3 Integration tests

Use a temporary SQLite database and fake site adapter to verify incremental synchronization, overlap de-duplication, outbox persistence, process-restart recovery, send reconciliation, and status degradation.

### 12.4 Controlled live tests

Live account tests are read-only by default. A send test requires an explicitly configured test conversation and test recipient. Credentials and live customer content never become fixtures.

On live failures, capture a screenshot and Playwright trace only when enabled; store them in the protected application-data directory and apply retention rules.

## 13. Acceptance Criteria

The first release is accepted when:

1. An authenticated CRM caller can page through synchronized orders and conversations and read message history.
2. An authenticated agent caller can enqueue an allowlisted low-risk message and observe its final job state.
3. Sensitive or non-allowlisted content returns `requires_human_review` without browser submission.
4. Repeating the same synchronization or idempotent send request does not duplicate records or sends.
5. Restarting the process preserves records, checkpoints, audit history, and safe queued jobs.
6. New inquiry messages normally appear in the API within 60 seconds under healthy site conditions.
7. Login loss, verification challenges, adapter incompatibility, stalled synchronization, and uncertain sends are distinguishable through `/v1/status`.
8. The API does not expose browser credentials, arbitrary automation primitives, or unredacted secrets.
9. The service starts automatically in the dedicated interactive Windows session and can be manually recovered after an authentication interruption.

## 14. Project Structure

The implementation will keep site-specific behavior isolated from API and persistence concerns:

```text
src/mic_gateway/
  api/
  browser/
  adapters/made_in_china/
  sync/
  messaging/
  policies/
  db/
  monitoring/
tests/
  unit/
  integration/
  contract/
  live/
```

The planned runtime stack is Python 3.12, FastAPI, Uvicorn, Playwright for Python, SQLAlchemy, Alembic, Pydantic Settings, and SQLite. No external queue or cache is required for the single-account first release.

## 15. Scope Boundary for Implementation Planning

One implementation plan may cover the first release because all components serve one account and one gateway process. Live site discovery will identify concrete selectors and request contracts, but it will not change the public API or safety boundaries defined here. If discovery shows that orders and inquiries require fundamentally separate authentication contexts or incompatible browser lifecycles, implementation planning must split them into separately deployable adapters while preserving this public contract.
