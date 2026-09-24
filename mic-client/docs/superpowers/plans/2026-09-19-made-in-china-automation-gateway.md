# Made-in-China Automation Gateway Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a single-account Windows service that synchronizes Made-in-China orders and inquiry conversations into a local database, exposes them to a CRM through FastAPI, and safely sends allowlisted agent messages.

**Architecture:** A FastAPI process reads and writes an async SQLite store while one serialized Playwright worker owns a persistent Chromium profile. A Made-in-China adapter hides request-level and DOM automation details; schedulers synchronize source data and drain an idempotent outbox. Development defaults to a fake adapter and sanitized fixtures; live discovery may run on the development computer after the operator logs into its dedicated profile, while final deployment validation still runs on the always-on target Windows computer.

**Tech Stack:** Python 3.12, FastAPI, Uvicorn, Playwright for Python, SQLAlchemy 2 async, Alembic, SQLite/aiosqlite, Pydantic Settings, Argon2, pytest, pytest-asyncio, HTTPX, Ruff, mypy

**Spec:** `docs/superpowers/specs/2026-09-19-made-in-china-automation-gateway-design.md`

## Global Constraints

- Support exactly one Made-in-China seller account and one serialized browser worker.
- Bind to `0.0.0.0` by default on configurable port `8787`; never expose the Playwright debugging interface.
- Require `X-API-Key` for every `/v1/*` endpoint with roles `crm_read`, `agent_send`, and `admin`.
- Keep Chromium profile, SQLite database, logs, screenshots, and traces outside the source tree under a configurable application-data directory.
- Do not reuse a personal Chrome profile; the operator logs into a dedicated persistent profile on each computer used for live discovery or production automation.
- Do not bypass CAPTCHAs, verification challenges, access controls, or platform risk controls.
- Synchronize conversations/messages every 30 seconds and orders every 5 minutes by default.
- Automatically send only `greeting`, `acknowledgement`, `holiday_wish`, and `non_commercial_followup` intents after deterministic content checks.
- Never blindly retry an `uncertain` send; reconcile it against the conversation first.
- Keep API and adapter contracts stable when live site selectors or undocumented JSON requests change.
- Do not modify the existing CRM, create a custom UI, or add Redis/Celery/webhooks in the first release.
- Run live account tests read-only unless an explicit test conversation and recipient are configured.

## Review Focus

- Two concurrent requests with one idempotency key must create one job; a different payload with that key must return HTTP 409.
- A click followed by lost confirmation must become `uncertain` and remain unsent until reconciliation proves the outcome.
- Login loss, CAPTCHA, or verification must pause browser work and return `operator_action_required`, never trigger a bypass or endless retry.
- Malformed cursors, invalid timestamps, oversized messages, and unknown enum values must return stable 4xx errors instead of HTTP 500.
- Missing, revoked, wrong-role, or rate-limited API keys must not reveal business data or whether a conversation exists.

---

## Planned File Map

```text
pyproject.toml                         package metadata, runtime and test dependencies
.gitignore                             secrets and runtime-artifact exclusions
.env.example                           documented non-secret configuration names
alembic.ini                            migration runner configuration
alembic/env.py                         async migration environment
alembic/versions/0001_initial.py       initial operational schema
src/mic_gateway/__init__.py            package marker and version
src/mic_gateway/main.py                application factory and lifespan wiring
src/mic_gateway/config.py              validated environment configuration
src/mic_gateway/cli.py                 database, key, browser-login, and diagnostics commands
src/mic_gateway/domain.py              shared enums and immutable source/domain records
src/mic_gateway/errors.py              stable service exceptions and API codes
src/mic_gateway/db/base.py             SQLAlchemy base and session factory
src/mic_gateway/db/models.py           ORM tables
src/mic_gateway/db/repositories.py     queries, upserts, cursor pagination, and job transitions
src/mic_gateway/api/schemas.py         public Pydantic request/response models
src/mic_gateway/api/auth.py            API-key verification and role enforcement
src/mic_gateway/api/middleware.py      request IDs, body limits, and rate limiting
src/mic_gateway/api/routes_health.py   liveness and readiness endpoints
src/mic_gateway/api/routes_read.py     order, conversation, message, job, and status reads
src/mic_gateway/api/routes_write.py    message submission and admin synchronization
src/mic_gateway/policies/messages.py   allowlisted intents and deterministic risk checks
src/mic_gateway/adapters/base.py       stable site-adapter protocol
src/mic_gateway/adapters/fake.py       deterministic development/test adapter
src/mic_gateway/adapters/made_in_china/selectors.py  live selector/request contract registry
src/mic_gateway/adapters/made_in_china/adapter.py    hybrid production adapter
src/mic_gateway/browser/runtime.py     persistent Playwright context and serialized execution
src/mic_gateway/browser/discovery.py   target-only redacted discovery capture
src/mic_gateway/sync/engine.py         incremental synchronization and checkpoints
src/mic_gateway/messaging/outbox.py    send, confirmation, and reconciliation state machine
src/mic_gateway/monitoring/status.py   aggregate operational status
src/mic_gateway/runtime/scheduler.py   interval loops, backoff, and shutdown
tests/unit/                            pure configuration, policy, cursor, auth, and state tests
tests/integration/                     SQLite/API/worker tests with fake adapter
tests/contract/                        sanitized Made-in-China fixtures and parser contracts
tests/live/                            opt-in authenticated-computer smoke tests
scripts/install-windows.ps1            virtualenv, Playwright, directories, and ACL setup
scripts/register-task.ps1              interactive-logon scheduled-task registration
scripts/configure-firewall.ps1         explicit trusted-source firewall rule
docs/operations.md                     startup, login, recovery, rotation, and upgrade runbook
```

### Task 1: Project foundation, configuration, and liveness

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `.env.example`
- Create: `src/mic_gateway/__init__.py`
- Create: `src/mic_gateway/config.py`
- Create: `src/mic_gateway/main.py`
- Create: `src/mic_gateway/api/routes_health.py`
- Test: `tests/unit/test_config.py`
- Test: `tests/integration/test_health_api.py`

**Interfaces:**
- Consumes: none
- Produces: `Settings`, `get_settings()`, and `create_app(settings: Settings | None = None) -> FastAPI`

- [ ] **Step 1: Add failing configuration tests**

```python
def test_defaults_bind_to_all_interfaces(tmp_path):
    settings = Settings(app_data_dir=tmp_path)
    assert settings.host == "0.0.0.0"
    assert settings.port == 8787
    assert settings.conversation_sync_seconds == 30
    assert settings.order_sync_seconds == 300

def test_source_tree_cannot_be_runtime_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ValueError, match="outside the source tree"):
        Settings(app_data_dir=tmp_path / "runtime")
```

- [ ] **Step 2: Add package metadata and install the editable development environment**

```toml
[project]
name = "mic-gateway"
version = "0.1.0"
requires-python = ">=3.12,<3.13"
dependencies = [
  "fastapi>=0.116,<1",
  "uvicorn[standard]>=0.35,<1",
  "playwright>=1.55,<2",
  "sqlalchemy[asyncio]>=2.0,<3",
  "aiosqlite>=0.21,<1",
  "alembic>=1.16,<2",
  "pydantic-settings>=2.10,<3",
  "argon2-cffi>=25.1,<26",
  "structlog>=25.4,<26",
]

[project.optional-dependencies]
dev = ["pytest>=8.4,<9", "pytest-asyncio>=1.1,<2", "pytest-cov>=6.2,<7", "httpx>=0.28,<1", "ruff>=0.12,<1", "mypy>=1.17,<2"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
markers = [
  "live: requires an operator-authenticated automation computer",
  "live_send: sends one message to the configured test conversation",
]
```

Run: `py -3.12 -m venv .venv` then `.\.venv\Scripts\python.exe -m pip install -e ".[dev]"`

- [ ] **Step 3: Implement validated settings and artifact exclusions**

```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MIC_", env_file=".env", extra="forbid")
    app_data_dir: Path
    host: str = "0.0.0.0"
    port: int = 8787
    conversation_sync_seconds: int = 30
    order_sync_seconds: int = 300
    database_url: str | None = None
    chromium_headless: bool = False
    max_request_bytes: int = 65_536
```

Add `.env`, `.venv/`, `*.db*`, `runtime/`, `playwright-report/`, `test-results/`, screenshots, traces, and browser profiles to `.gitignore`. Document `MIC_APP_DATA_DIR` and non-secret defaults in `.env.example`.

- [ ] **Step 4: Add a minimal application factory and liveness test**

```python
@router.get("/health/live")
async def live() -> dict[str, str]:
    return {"status": "alive"}

async def test_liveness_needs_no_api_key(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "alive"}
```

- [ ] **Step 5: Run quality checks and commit**

Run: `.\.venv\Scripts\python.exe -m pytest tests/unit/test_config.py tests/integration/test_health_api.py -v`

Run: `.\.venv\Scripts\python.exe -m ruff check src tests`

Commit: `git add pyproject.toml .gitignore .env.example src tests && git commit -m "chore: bootstrap gateway service"`

### Task 2: Domain types, SQLite schema, and migrations

**Files:**
- Create: `src/mic_gateway/domain.py`
- Create: `src/mic_gateway/db/base.py`
- Create: `src/mic_gateway/db/models.py`
- Create: `alembic.ini`
- Create: `alembic/env.py`
- Create: `alembic/versions/0001_initial.py`
- Test: `tests/integration/test_database_schema.py`

**Interfaces:**
- Consumes: `Settings`
- Produces: `Role`, `MessageIntent`, `JobState`, `ServiceState`, `Direction`, `SourceOrder`, `SourceConversation`, `SourceMessage`, `create_engine_and_sessionmaker(settings)`

- [ ] **Step 1: Write schema and enum tests before creating models**

```python
async def test_initial_migration_creates_operational_tables(migrated_engine):
    names = set(await table_names(migrated_engine))
    assert names == {
        "api_keys", "orders", "order_lines", "conversations", "messages",
        "sync_checkpoints", "outbox_jobs", "audit_events", "runtime_status",
    }

def test_public_enum_values_are_stable():
    assert MessageIntent.HOLIDAY_WISH.value == "holiday_wish"
    assert JobState.UNCERTAIN.value == "uncertain"
```

- [ ] **Step 2: Define exact shared enums and source records**

```python
class Role(StrEnum):
    CRM_READ = "crm_read"
    AGENT_SEND = "agent_send"
    ADMIN = "admin"

class MessageIntent(StrEnum):
    GREETING = "greeting"
    ACKNOWLEDGEMENT = "acknowledgement"
    HOLIDAY_WISH = "holiday_wish"
    NON_COMMERCIAL_FOLLOWUP = "non_commercial_followup"

class JobState(StrEnum):
    QUEUED = "queued"
    SENDING = "sending"
    SENT = "sent"
    REQUIRES_HUMAN_REVIEW = "requires_human_review"
    FAILED = "failed"
    UNCERTAIN = "uncertain"
```

Define frozen dataclasses for source orders, conversations, and messages. Each contains `source_id`, timezone-aware source timestamps, normalized fields, and a `raw_snapshot: dict[str, object]` that has already been sanitized. `SourceMessage` also carries direction, sender label, text, and attachment metadata; it never downloads attachments automatically.

- [ ] **Step 3: Implement ORM tables with database-enforced uniqueness**

```python
class OutboxJob(Base):
    __tablename__ = "outbox_jobs"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    payload_digest: Mapped[str] = mapped_column(String(64))
    conversation_id: Mapped[UUID] = mapped_column(ForeignKey("conversations.id"))
    intent: Mapped[str] = mapped_column(String(64))
    content: Mapped[str] = mapped_column(Text)
    state: Mapped[str] = mapped_column(String(32), index=True)
    attempt_count: Mapped[int] = mapped_column(default=0)
```

Add unique constraints on every source ID, on `(conversation_id, source_id)` for inbound messages, and on a fallback content fingerprint when the source supplies no message ID.

- [ ] **Step 4: Create and run the initial migration against a temporary database**

Run: `.\.venv\Scripts\python.exe -m alembic upgrade head`

Expected: exit code 0 and all nine tables exist.

- [ ] **Step 5: Run tests and commit**

Run: `.\.venv\Scripts\python.exe -m pytest tests/integration/test_database_schema.py -v`

Commit: `git add src/mic_gateway/domain.py src/mic_gateway/db alembic.ini alembic tests && git commit -m "feat: add gateway persistence schema"`

### Task 3: API-key provisioning, authorization, request IDs, and limits

**Files:**
- Create: `src/mic_gateway/errors.py`
- Create: `src/mic_gateway/api/auth.py`
- Create: `src/mic_gateway/api/middleware.py`
- Create: `src/mic_gateway/api/schemas.py`
- Create: `src/mic_gateway/cli.py`
- Modify: `src/mic_gateway/main.py`
- Test: `tests/unit/test_auth.py`
- Test: `tests/integration/test_api_security.py`

**Interfaces:**
- Consumes: `Role`, `api_keys` table, `Settings`
- Produces: `Principal`, `require_role(*roles)`, `ApiError`, `create_api_key(session, name, role) -> str`, `RequestContextMiddleware`, `RateLimiter`

- [ ] **Step 1: Write failing key and disclosure tests**

```python
async def test_plaintext_key_is_returned_once(session):
    raw = await create_api_key(session, "crm", Role.CRM_READ)
    row = await load_key_by_name(session, "crm")
    assert raw.startswith("mic_")
    assert raw not in row.key_hash

@pytest.mark.parametrize("header", [None, "invalid", "revoked-key"])
async def test_unauthorized_call_does_not_disclose_resource(app, header):
    response = await get_order(app, "known-order", header)
    assert response.status_code == 401
    assert "known-order" not in response.text
```

- [ ] **Step 2: Implement Argon2 key hashing and role dependencies**

Generate 32 random bytes with `secrets.token_urlsafe(32)`, prefix with `mic_`, store only the Argon2 hash plus a non-secret key prefix for candidate lookup, and compare verified hashes through Argon2. Role inheritance is `admin` > `agent_send` > `crm_read`.

```python
@dataclass(frozen=True)
class Principal:
    key_id: UUID
    name: str
    role: Role

def require_role(*allowed: Role) -> Callable[..., Awaitable[Principal]]:
    async def dependency(principal: Principal = Depends(authenticate)) -> Principal:
        if not role_allows(principal.role, allowed):
            raise ApiError(403, "forbidden", "The API key lacks this permission")
        return principal
    return dependency
```

- [ ] **Step 3: Add request IDs, body-size checks, and per-key rate limits**

Use `X-Request-ID` when it matches `^[A-Za-z0-9._-]{1,64}$`; otherwise generate a UUID. Reject bodies over 65,536 bytes with code `request_too_large`. Configure sliding windows of 120 reads/minute, 10 send submissions/minute, and 3 admin sync submissions/minute per key.

- [ ] **Step 4: Add the provisioning CLI and exercise it**

```powershell
.\.venv\Scripts\python.exe -m mic_gateway.cli create-api-key --name crm --role crm_read
.\.venv\Scripts\python.exe -m mic_gateway.cli create-api-key --name agent --role agent_send
.\.venv\Scripts\python.exe -m mic_gateway.cli create-api-key --name operator --role admin
```

Expected: each command prints one plaintext key once and never logs it again.

- [ ] **Step 5: Pin wrong-role and rate-limit behavior**

```python
async def test_crm_key_cannot_submit_message(client_with_crm_key):
    response = await client_with_crm_key.post("/v1/conversations/c1/messages", json=valid_send)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"

async def test_send_rate_limit_hides_resource_state(agent_client):
    responses = [await agent_client.post("/v1/conversations/missing/messages", json=valid_send) for _ in range(11)]
    assert responses[-1].status_code == 429
    assert responses[-1].json()["error"]["code"] == "rate_limited"
```

- [ ] **Step 6: Run tests and commit**

Run: `.\.venv\Scripts\python.exe -m pytest tests/unit/test_auth.py tests/integration/test_api_security.py -v`

Commit: `git add src/mic_gateway/errors.py src/mic_gateway/api src/mic_gateway/cli.py src/mic_gateway/main.py tests && git commit -m "feat: secure gateway API access"`

### Task 4: Repositories, upserts, and cursor pagination

**Files:**
- Create: `src/mic_gateway/db/repositories.py`
- Test: `tests/integration/test_repositories.py`
- Test: `tests/unit/test_cursors.py`

**Interfaces:**
- Consumes: source/domain records and ORM models
- Produces: `OrderRepository`, `ConversationRepository`, `MessageRepository`, `CheckpointRepository`, `OutboxRepository`, `encode_cursor(updated_at, row_id)`, `decode_cursor(value)`

- [ ] **Step 1: Write de-duplication, ordering, and malformed-cursor tests**

```python
async def test_order_upsert_updates_without_duplication(order_repo, source_order):
    first = await order_repo.upsert(source_order)
    second = await order_repo.upsert(replace(source_order, status="shipped"))
    assert first.id == second.id
    assert await order_repo.count() == 1

def test_malformed_cursor_is_a_client_error():
    with pytest.raises(ApiError) as exc:
        decode_cursor("not-base64-json")
    assert exc.value.status_code == 422
    assert exc.value.code == "invalid_cursor"
```

- [ ] **Step 2: Implement stable opaque cursor encoding**

Encode compact JSON `{"u":"<UTC ISO timestamp>","i":"<UUID>"}` with URL-safe base64 and no padding. Decode with strict key, UUID, and timezone-aware timestamp validation. Repository ordering is `(source_updated_at DESC, id DESC)` and the next query uses the last pair as a seek cursor.

- [ ] **Step 3: Implement transactional source upserts**

Use SQLite `INSERT ... ON CONFLICT DO UPDATE` for orders, conversations, and messages. Never overwrite a newer `source_updated_at` with an older overlapping-window result. Store JSON snapshots only after calling `sanitize_snapshot()`.

- [ ] **Step 4: Add concurrent idempotency coverage at the database boundary**

```python
async def test_concurrent_same_key_creates_one_job(outbox_repo, request):
    results = await asyncio.gather(
        outbox_repo.create_idempotent(request),
        outbox_repo.create_idempotent(request),
    )
    assert results[0].job.id == results[1].job.id
    assert await outbox_repo.count() == 1
```

For the SQLite lock loser, catch the uniqueness error, roll back, reload by key, and compare payload digests.

- [ ] **Step 5: Run tests and commit**

Run: `.\.venv\Scripts\python.exe -m pytest tests/unit/test_cursors.py tests/integration/test_repositories.py -v`

Commit: `git add src/mic_gateway/db/repositories.py tests && git commit -m "feat: add idempotent gateway repositories"`

### Task 5: CRM read API and public response schemas

**Files:**
- Modify: `src/mic_gateway/api/schemas.py`
- Create: `src/mic_gateway/api/routes_read.py`
- Modify: `src/mic_gateway/main.py`
- Test: `tests/integration/test_read_api.py`

**Interfaces:**
- Consumes: read repositories, `require_role`, domain enums
- Produces: `/v1/orders`, `/v1/orders/{order_id}`, `/v1/conversations`, `/v1/conversations/{conversation_id}/messages`, `/v1/jobs/{job_id}`

- [ ] **Step 1: Write API contract tests for filtering and pagination**

```python
async def test_orders_return_deterministic_cursor_page(crm_client, seeded_orders):
    first = await crm_client.get("/v1/orders", params={"limit": 2})
    second = await crm_client.get("/v1/orders", params={"limit": 2, "cursor": first.json()["next_cursor"]})
    ids = [item["id"] for item in first.json()["items"] + second.json()["items"]]
    assert ids == list(dict.fromkeys(ids))

async def test_invalid_updated_after_returns_422(crm_client):
    response = await crm_client.get("/v1/orders?updated_after=yesterday")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
```

- [ ] **Step 2: Define public schemas without leaking raw snapshots**

`OrderResponse`, `OrderLineResponse`, `ConversationResponse`, `MessageResponse`, `JobResponse`, and `CursorPage[T]` contain normalized fields only. Do not include database paths, raw snapshots, selectors, cookies, request headers, or adapter diagnostics.

- [ ] **Step 3: Implement read routes and not-found behavior after authorization**

Validate the principal before looking up IDs. Return `404 resource_not_found` for a missing authorized resource. Limit pages to 1-200 items with default 50. Messages are ordered by `(source_created_at ASC, id ASC)`.

- [ ] **Step 4: Run OpenAPI and response-model tests**

Run: `.\.venv\Scripts\python.exe -m pytest tests/integration/test_read_api.py -v`

Assert the generated schema documents `X-API-Key`, stable enum values, cursor parameters, and response models.

- [ ] **Step 5: Commit**

Commit: `git add src/mic_gateway/api src/mic_gateway/main.py tests/integration/test_read_api.py && git commit -m "feat: expose CRM read endpoints"`

### Task 6: Message policy and idempotent send submission

**Files:**
- Create: `src/mic_gateway/policies/messages.py`
- Create: `src/mic_gateway/api/routes_write.py`
- Modify: `src/mic_gateway/api/schemas.py`
- Modify: `src/mic_gateway/main.py`
- Test: `tests/unit/test_message_policy.py`
- Test: `tests/integration/test_send_api.py`

**Interfaces:**
- Consumes: `MessageIntent`, `OutboxRepository`, `require_role(Role.AGENT_SEND)`
- Produces: `PolicyDecision`, `evaluate_message(intent, content)`, and `POST /v1/conversations/{id}/messages`

- [ ] **Step 1: Pin allowed and blocked multilingual examples**

```python
@pytest.mark.parametrize("intent,text", [
    (MessageIntent.GREETING, "Hello, thank you for contacting us."),
    (MessageIntent.HOLIDAY_WISH, "Happy New Year 2027!"),
    (MessageIntent.ACKNOWLEDGEMENT, "收到您的消息，我们会由同事进一步跟进。"),
])
def test_low_risk_messages_are_allowed(intent, text):
    assert evaluate_message(intent, text).allowed is True

@pytest.mark.parametrize("text", [
    "Our price is USD 12.50 each.", "可以给您九折", "Delivery will be within 7 days.",
    "Please pay by wire transfer.", "We guarantee 500 units in stock.", "We can issue a refund.",
])
def test_commercial_commitments_require_human_review(text):
    decision = evaluate_message(MessageIntent.NON_COMMERCIAL_FOLLOWUP, text)
    assert decision.allowed is False
    assert decision.code == "requires_human_review"
```

- [ ] **Step 2: Implement fail-closed deterministic policy**

Normalize Unicode and whitespace, cap content at 4,000 characters, and scan case-insensitively for currency formats, price/discount language, payments, delivery commitments, stock/capacity promises, contracts/warranties, refunds, and disputes in English and Chinese. Invalid policy configuration raises `PolicyUnavailable` and blocks the send.

- [ ] **Step 3: Write idempotency conflict and oversized-message API tests**

```python
async def test_same_key_different_payload_returns_conflict(agent_client, conversation):
    first = await submit(agent_client, conversation.id, "key-1", "Hello")
    second = await submit(agent_client, conversation.id, "key-1", "Different hello")
    assert first.status_code == 202
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "idempotency_conflict"

async def test_oversized_message_returns_422(agent_client, conversation):
    response = await submit(agent_client, conversation.id, "key-2", "x" * 4001)
    assert response.status_code == 422
```

- [ ] **Step 4: Implement send submission without touching the browser**

Compute the payload digest from canonical JSON containing conversation ID, intent, content, and caller reference. For blocked content, persist a terminal `requires_human_review` job and audit event. For allowed content, persist `queued` and return HTTP 202. A repeated equivalent request returns the existing job. Persist an audit event for every policy result and every later job-state transition, keyed by safe request ID and caller identity.

- [ ] **Step 5: Run tests and commit**

Run: `.\.venv\Scripts\python.exe -m pytest tests/unit/test_message_policy.py tests/integration/test_send_api.py -v`

Commit: `git add src/mic_gateway/policies src/mic_gateway/api tests && git commit -m "feat: gate and queue agent messages"`

### Task 7: Stable site-adapter protocol and fake adapter

**Files:**
- Create: `src/mic_gateway/adapters/base.py`
- Create: `src/mic_gateway/adapters/fake.py`
- Test: `tests/unit/test_adapter_contract.py`

**Interfaces:**
- Consumes: source/domain records
- Produces: `SiteAdapter`, `SourceCheckpoint`, `SourcePage[T]`, `SessionHealth`, `SendAttempt`, `FakeSiteAdapter`

- [ ] **Step 1: Write protocol-level fake-adapter tests**

```python
async def test_fake_adapter_pages_from_checkpoint(fake_adapter):
    page = await fake_adapter.list_conversations(SourceCheckpoint(cursor=None, updated_after=None))
    assert page.items[0].source_id == "conversation-1"
    assert page.next_cursor == "conversation-page-2"

async def test_fake_adapter_can_model_uncertain_send(fake_adapter):
    fake_adapter.next_send = SendAttempt.uncertain("confirmation_missing")
    result = await fake_adapter.send_message("conversation-1", "Hello")
    assert result.outcome == "uncertain"
```

- [ ] **Step 2: Define the exact async protocol**

```python
class SiteAdapter(Protocol):
    async def check_session(self) -> SessionHealth: ...
    async def list_orders(self, checkpoint: SourceCheckpoint) -> SourcePage[SourceOrder]: ...
    async def list_conversations(self, checkpoint: SourceCheckpoint) -> SourcePage[SourceConversation]: ...
    async def list_messages(self, conversation_source_id: str, checkpoint: SourceCheckpoint) -> SourcePage[SourceMessage]: ...
    async def send_message(self, conversation_source_id: str, content: str) -> SendAttempt: ...
    async def find_outbound_match(self, conversation_source_id: str, content_digest: str, earliest: datetime) -> SourceMessage | None: ...
```

- [ ] **Step 3: Implement a deterministic in-memory fake**

The fake accepts seeded pages, records method calls, supports injected session states and failures, and never imports Playwright. This becomes the only adapter used by development integration tests.

- [ ] **Step 4: Run tests and commit**

Run: `.\.venv\Scripts\python.exe -m pytest tests/unit/test_adapter_contract.py -v`

Commit: `git add src/mic_gateway/adapters tests/unit/test_adapter_contract.py && git commit -m "feat: define site adapter boundary"`

### Task 8: Incremental synchronization, checkpoints, and backoff

**Files:**
- Create: `src/mic_gateway/sync/engine.py`
- Test: `tests/integration/test_sync_engine.py`

**Interfaces:**
- Consumes: `SiteAdapter`, order/conversation/message repositories, `CheckpointRepository`
- Produces: `SyncEngine.sync_orders()`, `sync_conversations_and_messages()`, `BackoffPolicy.next_delay(failure_count)`

- [ ] **Step 1: Write overlap, de-duplication, and restart tests**

```python
async def test_restart_resumes_from_committed_checkpoint(engine_factory, fake_adapter):
    first = engine_factory(fake_adapter)
    await first.sync_orders()
    second = engine_factory(fake_adapter)
    await second.sync_orders()
    assert fake_adapter.order_checkpoints[-1].cursor == "orders-page-2"

async def test_older_overlap_record_does_not_replace_newer_row(sync_engine, order_repo):
    await sync_engine.sync_orders()
    await sync_engine.sync_orders()
    order = await order_repo.get_by_source_id("order-1")
    assert order.status == "newer-status"
```

- [ ] **Step 2: Implement page transactions and checkpoint ordering**

For each page, upsert all items and update its checkpoint in one transaction. If either fails, roll back both. For conversations, upsert the conversation before synchronizing its messages. The overlap window defaults to 10 minutes when a source cursor is unavailable.

- [ ] **Step 3: Implement bounded exponential backoff**

```python
@dataclass(frozen=True)
class BackoffPolicy:
    base_seconds: int = 5
    maximum_seconds: int = 300

    def next_delay(self, failure_count: int) -> int:
        return min(self.maximum_seconds, self.base_seconds * (2 ** max(0, failure_count - 1)))
```

Reset failure count after success. Map authentication and verification failures to a paused checkpoint with `operator_action_required`; do not schedule automatic retries until session health clears.

- [ ] **Step 4: Test stale status inputs**

Assert conversation sync older than 120 seconds and order sync older than 900 seconds are degraded. These thresholds are configurable and are evaluated using UTC monotonic comparisons where possible.

- [ ] **Step 5: Run tests and commit**

Run: `.\.venv\Scripts\python.exe -m pytest tests/integration/test_sync_engine.py -v`

Commit: `git add src/mic_gateway/sync tests/integration/test_sync_engine.py && git commit -m "feat: synchronize source data incrementally"`

### Task 9: Persistent Playwright runtime and operator login command

**Files:**
- Create: `src/mic_gateway/browser/runtime.py`
- Modify: `src/mic_gateway/cli.py`
- Test: `tests/unit/test_browser_runtime.py`
- Test: `tests/integration/test_browser_serialization.py`

**Interfaces:**
- Consumes: `Settings`
- Produces: `BrowserRuntime.start()`, `stop()`, `run_serialized(operation)`, `session_state`, and CLI command `browser-login`

- [ ] **Step 1: Write lifecycle and serialization tests with a fake Playwright launcher**

```python
async def test_operations_never_overlap(browser_runtime):
    active = 0
    peak = 0
    async def operation(page):
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0.01)
        active -= 1
    await asyncio.gather(*(browser_runtime.run_serialized(operation) for _ in range(5)))
    assert peak == 1
```

- [ ] **Step 2: Implement the dedicated persistent context**

Launch with `async_playwright().start()` and `chromium.launch_persistent_context(user_data_dir=settings.browser_profile_dir, headless=settings.chromium_headless)`. Use one retained page, close cleanly on shutdown, and never enable a remote debugging port.

- [ ] **Step 3: Add fail-closed session-state transitions**

States are `starting`, `authenticated`, `operator_action_required`, `site_contract_error`, and `stopped`. A runtime crash rejects new browser operations and updates status before restart logic runs.

- [ ] **Step 4: Add the authenticated-computer login command**

Run on the development computer for live discovery and repeat on the target computer for production:

```powershell
.\.venv\Scripts\python.exe -m playwright install chromium
.\.venv\Scripts\python.exe -m mic_gateway.cli browser-login
```

The command opens the dedicated headed profile, navigates to the configured Made-in-China seller URL, and waits for the operator to confirm login from the terminal. It then calls `check_session`; success exits 0, while a missing authenticated marker exits nonzero without copying cookies from personal Chrome.

- [ ] **Step 5: Run non-live tests and commit**

Run: `.\.venv\Scripts\python.exe -m pytest tests/unit/test_browser_runtime.py tests/integration/test_browser_serialization.py -v`

Commit: `git add src/mic_gateway/browser src/mic_gateway/cli.py tests && git commit -m "feat: manage persistent browser session"`

### Task 10: Outbox delivery and uncertain-send reconciliation

**Files:**
- Create: `src/mic_gateway/messaging/outbox.py`
- Test: `tests/integration/test_outbox_worker.py`

**Interfaces:**
- Consumes: `OutboxRepository`, `SiteAdapter`, `BrowserRuntime`
- Produces: `OutboxWorker.run_once()`, `reconcile_uncertain(job_id)`, `recover_after_restart()`

- [ ] **Step 1: Write success, confirmed failure, and uncertain-send tests**

```python
async def test_uncertain_send_is_not_automatically_retried(worker, fake_adapter, queued_job):
    fake_adapter.next_send = SendAttempt.uncertain("confirmation_missing")
    await worker.run_once()
    await worker.run_once()
    assert fake_adapter.send_calls == 1
    assert (await worker.jobs.get(queued_job.id)).state == JobState.UNCERTAIN

async def test_reconciliation_marks_matching_message_sent_without_resend(worker, fake_adapter, uncertain_job):
    fake_adapter.outbound_match = matching_source_message(uncertain_job)
    await worker.reconcile_uncertain(uncertain_job.id)
    assert fake_adapter.send_calls == 0
    assert (await worker.jobs.get(uncertain_job.id)).state == JobState.SENT
```

- [ ] **Step 2: Implement atomic job claiming**

Select the oldest `queued` job and atomically transition it to `sending` in a short transaction. Enforce one in-flight send through the serialized browser worker. Wait at least 10 seconds between actual website sends; configuration may increase but not reduce this floor.

- [ ] **Step 3: Implement terminal and retry decisions**

`sent` is terminal after source confirmation. Explicit transient failures return to `queued` with bounded backoff and incremented attempts. Explicit permanent failures become `failed`. Missing confirmation becomes `uncertain` and is never selected by the ordinary send loop.

- [ ] **Step 4: Implement restart recovery**

On startup, move abandoned `sending` jobs to `uncertain`, not `queued`, because the previous process may have clicked Send before it stopped. Reconciliation checks for a matching outbound digest at or after the original attempt time.

- [ ] **Step 5: Run tests and commit**

Run: `.\.venv\Scripts\python.exe -m pytest tests/integration/test_outbox_worker.py -v`

Commit: `git add src/mic_gateway/messaging tests/integration/test_outbox_worker.py && git commit -m "feat: deliver messages through safe outbox"`

### Task 11: Status aggregation, scheduler, admin sync, and application lifespan

**Files:**
- Create: `src/mic_gateway/monitoring/status.py`
- Create: `src/mic_gateway/runtime/scheduler.py`
- Modify: `src/mic_gateway/api/routes_health.py`
- Modify: `src/mic_gateway/api/routes_read.py`
- Modify: `src/mic_gateway/api/routes_write.py`
- Modify: `src/mic_gateway/main.py`
- Test: `tests/integration/test_runtime_status.py`
- Test: `tests/integration/test_scheduler.py`

**Interfaces:**
- Consumes: browser state, checkpoints, outbox state, API auth, sync engine
- Produces: `/health/ready`, `/v1/status`, `POST /v1/admin/sync`, `GatewayScheduler.start()/stop()`

- [ ] **Step 1: Write operator-action and stale-sync status tests**

```python
async def test_verification_challenge_pauses_work_and_surfaces_status(running_gateway):
    running_gateway.adapter.session_health = SessionHealth.verification_required()
    await running_gateway.scheduler.tick()
    status = await running_gateway.admin_client.get("/v1/status")
    assert status.json()["state"] == "operator_action_required"
    assert running_gateway.adapter.send_calls == 0

async def test_readiness_fails_when_database_is_unavailable(app_with_broken_db):
    response = await app_with_broken_db.get("/health/ready")
    assert response.status_code == 503
```

- [ ] **Step 2: Implement scheduler loops with independent cadence**

Use `asyncio.TaskGroup` for conversations, orders, outbox, and health refresh. Each loop waits on a shutdown event with timeout rather than sleeping uninterruptibly. Manual sync writes a deduplicated command consumed by the scheduler and returns HTTP 202.

- [ ] **Step 3: Aggregate safe status**

Return browser/session state, last attempt/success per resource, failure counts and safe codes, queued/sending/uncertain job counts, and freshness state. Never return source URLs containing tokens, selectors, cookies, paths to browser profiles, or customer message bodies.

- [ ] **Step 4: Wire application lifespan in deterministic order**

Startup order: validate settings, create app-data directories, migrate/check database, recover outbox, start browser runtime, check session, then start scheduler. Shutdown order: stop accepting mutation work, stop scheduler, finish/mark in-flight work safely, close browser, dispose database engine.

- [ ] **Step 5: Run integration suite and commit**

Run: `.\.venv\Scripts\python.exe -m pytest tests/integration/test_runtime_status.py tests/integration/test_scheduler.py -v`

Commit: `git add src/mic_gateway/monitoring src/mic_gateway/runtime src/mic_gateway/api src/mic_gateway/main.py tests && git commit -m "feat: operate and monitor gateway runtime"`

### Task 12: Target-computer discovery recorder and sanitization

**Files:**
- Create: `src/mic_gateway/browser/discovery.py`
- Modify: `src/mic_gateway/cli.py`
- Create: `tests/unit/test_discovery_sanitization.py`
- Create on an authenticated computer after review: `tests/contract/fixtures/orders-page.sanitized.json`
- Create on an authenticated computer after review: `tests/contract/fixtures/conversations-page.sanitized.json`
- Create on an authenticated computer after review: `tests/contract/fixtures/messages-page.sanitized.json`
- Create on an authenticated computer after review: `tests/contract/fixtures/conversation-page.sanitized.html`

**Interfaces:**
- Consumes: authenticated `BrowserRuntime`
- Produces: `sanitize_capture(value)`, CLI `discover --resource orders|conversations|messages`, reviewed sanitized contract fixtures

- [ ] **Step 1: Write sanitization tests before any live capture**

```python
def test_capture_removes_credentials_and_customer_pii():
    capture = {"authorization": "Bearer secret", "cookie": "sid=secret", "email": "buyer@example.com", "phone": "+86 13800138000", "id": "order-1"}
    result = sanitize_capture(capture)
    assert result == {"authorization": "[REDACTED]", "cookie": "[REDACTED]", "email": "[EMAIL]", "phone": "[PHONE]", "id": "order-1"}
```

- [ ] **Step 2: Implement opt-in redacted capture**

The recorder logs request method, URL origin/path without query secrets, response status/content type, and sanitized JSON shapes for candidate business endpoints. It writes only to the protected application-data directory. HTML capture keeps the smallest relevant subtree and replaces text, email, phone, buyer, company, address, and identifier values with deterministic synthetic values.

- [ ] **Step 3: Run discovery only on an operator-authorized authenticated computer**

```powershell
.\.venv\Scripts\python.exe -m mic_gateway.cli discover --resource orders
.\.venv\Scripts\python.exe -m mic_gateway.cli discover --resource conversations
.\.venv\Scripts\python.exe -m mic_gateway.cli discover --resource messages
```

During each run, the operator opens the relevant seller page and performs one ordinary read-only navigation. For message discovery, open the configured test conversation but do not send.

- [ ] **Step 4: Review before promoting sanitized fixtures into Git**

Run: `rg -n -i "authorization|cookie|token|session|@|phone|mobile|address" "$env:MIC_APP_DATA_DIR\discovery"`

Open every match, confirm secrets and PII are replaced, copy only the four listed sanitized fixtures into `tests/contract/fixtures/`, and run the same `rg` command against that directory. Do not commit a fixture with unexplained matches.

- [ ] **Step 5: Run tests and commit recorder separately from live fixtures**

Run: `.\.venv\Scripts\python.exe -m pytest tests/unit/test_discovery_sanitization.py -v`

Commit recorder: `git add src/mic_gateway/browser/discovery.py src/mic_gateway/cli.py tests/unit/test_discovery_sanitization.py && git commit -m "feat: add redacted site discovery tooling"`

After privacy review on the authenticated computer, commit fixtures: `git add tests/contract/fixtures && git commit -m "test: add sanitized Made-in-China contracts"`

### Task 13: Hybrid Made-in-China adapter using an authenticated computer

**Files:**
- Create: `src/mic_gateway/adapters/made_in_china/__init__.py`
- Create: `src/mic_gateway/adapters/made_in_china/selectors.py`
- Create: `src/mic_gateway/adapters/made_in_china/adapter.py`
- Create: `tests/contract/test_orders_contract.py`
- Create: `tests/contract/test_conversations_contract.py`
- Create: `tests/contract/test_messages_contract.py`
- Create: `tests/live/test_read_only_smoke.py`
- Create: `tests/live/test_send_smoke.py`

**Interfaces:**
- Consumes: `BrowserRuntime`, sanitized fixtures, `SiteAdapter` protocol
- Produces: `MadeInChinaAdapter` satisfying every `SiteAdapter` method

- [ ] **Step 1: Write fixture-based parser contract tests**

```python
def test_conversation_fixture_maps_stable_source_fields(conversation_fixture):
    result = parse_conversations(conversation_fixture)
    assert result.items[0].source_id == "conversation-001"
    assert result.items[0].buyer_reference == "buyer-001"
    assert result.items[0].source_updated_at.tzinfo is not None

def test_incompatible_shape_fails_closed():
    with pytest.raises(SiteContractError, match="conversation_list"):
        parse_conversations({"unexpected": []})
```

Write equivalent exact assertions for order IDs/status/lines and message IDs/direction/timestamps. Tests use only reviewed sanitized fixtures.

- [ ] **Step 2: Implement request-level reads from the discovered contract**

Put endpoint path patterns, response version markers, and required JSON keys in `selectors.py`. Execute fetches inside the authenticated browser context so the browser remains the authorization source. Validate status, content type, and required keys before normalization. Strip auth material from every raw snapshot.

- [ ] **Step 3: Implement validated DOM fallback for each read operation**

Use role, label, and stable data attributes observed in the sanitized HTML before CSS position selectors. After navigation, wait for a named page marker and either a validated item list or an explicit empty-state marker. If neither appears before timeout, raise `SiteContractError`; do not return an empty page.

- [ ] **Step 4: Implement visible-UI send and confirmation**

Navigate directly to the known conversation through the seller UI, wait for the conversation source ID marker, fill the composer, and click the visible Send control. Do not use an undocumented send endpoint in the first release. Confirm by rereading the conversation and matching normalized content digest plus send-attempt time. Return `uncertain` when confirmation is absent.

- [ ] **Step 5: Detect authentication and verification states before business operations**

Use positively identified authenticated navigation markers for success. Treat login form, verification text, CAPTCHA iframe, or redirected authentication URL as `operator_action_required`. Treat an unrecognized page as `site_contract_error`, not authenticated.

- [ ] **Step 6: Run contract and read-only live tests on the authenticated computer**

Run: `.\.venv\Scripts\python.exe -m pytest tests/contract -v`

Run: `.\.venv\Scripts\python.exe -m pytest tests/live/test_read_only_smoke.py -v --live`

The read-only smoke test asserts at least one endpoint completes with a structurally valid page; an account with no current rows may pass only when the adapter validates the site's explicit empty-state marker.

- [ ] **Step 7: Run one explicitly configured send smoke test**

Set `MIC_LIVE_TEST_CONVERSATION_ID` to the designated test conversation and `MIC_LIVE_TEST_RECIPIENT_LABEL` to its expected recipient, then run:

`.\.venv\Scripts\python.exe -m pytest tests/live/test_send_smoke.py -v --live-send`

The test sends a unique non-commercial acknowledgement, confirms it once, and skips unless both variables and the `--live-send` flag are present.

- [ ] **Step 8: Commit the production adapter**

Commit: `git add src/mic_gateway/adapters/made_in_china tests/contract tests/live && git commit -m "feat: integrate Made-in-China seller portal"`

### Task 14: Windows installation, Task Scheduler, firewall, and operations

**Files:**
- Create: `scripts/install-windows.ps1`
- Create: `scripts/register-task.ps1`
- Create: `scripts/configure-firewall.ps1`
- Create: `docs/operations.md`
- Test: `tests/unit/test_script_contracts.py`

**Interfaces:**
- Consumes: packaged gateway, target Windows account, `MIC_APP_DATA_DIR`
- Produces: repeatable target installation and recovery runbook

- [ ] **Step 1: Write static contract tests for safe script defaults**

```python
def test_firewall_script_requires_explicit_remote_addresses(repo_root):
    script = (repo_root / "scripts/configure-firewall.ps1").read_text()
    assert "[Parameter(Mandatory = $true)]" in script
    assert "RemoteAddress" in script
    assert "Any" not in script

def test_scheduled_task_uses_interactive_logon(repo_root):
    script = (repo_root / "scripts/register-task.ps1").read_text()
    assert "Interactive" in script
    assert "AtLogOn" in script
```

- [ ] **Step 2: Implement repeatable installation without embedding secrets**

`install-windows.ps1` accepts explicit `-InstallDir` and `-AppDataDir`, creates `.venv`, installs the package, runs `playwright install chromium`, creates operational directories, and grants access only to the current dedicated user and local administrators. It refuses a source-tree `AppDataDir`.

- [ ] **Step 3: Register an interactive scheduled task**

`register-task.ps1` registers the gateway for the dedicated user's logon, runs `.venv\Scripts\python.exe -m uvicorn mic_gateway.main:create_app --factory --host 0.0.0.0 --port 8787`, uses the repository as working directory, restarts after bounded failures, and never stores an API key in task arguments.

- [ ] **Step 4: Configure a narrowly scoped firewall rule**

`configure-firewall.ps1` requires `-RemoteAddress` and defaults to no remote ranges. It creates an inbound TCP rule for the configured port and supplied localhost/trusted-LAN addresses. Document that public-internet exposure requires VPN or TLS reverse proxy and is outside the first release.

- [ ] **Step 5: Write the operations runbook**

Document installation, database migration, key provisioning, one-time dedicated-profile login, startup verification, CRM base URL, API-key rotation, manual sync, status interpretation, CAPTCHA/login recovery, diagnostic retention, backup/restore, upgrade, rollback, and clean shutdown. Include exact commands from Tasks 1, 3, 9, 12, and 13.

- [ ] **Step 6: Run script-contract and full non-live verification**

Run: `.\.venv\Scripts\python.exe -m pytest -m "not live" -v`

Run: `.\.venv\Scripts\python.exe -m ruff check src tests`

Run: `.\.venv\Scripts\python.exe -m mypy src`

Run: `git status --short`

- [ ] **Step 7: Commit deployment assets**

Commit: `git add scripts docs/operations.md tests/unit/test_script_contracts.py && git commit -m "docs: add Windows gateway operations"`

### Task 15: End-to-end acceptance and release candidate

**Files:**
- Create: `tests/integration/test_acceptance_flow.py`
- Modify: `docs/operations.md`

**Interfaces:**
- Consumes: complete gateway with fake adapter, then complete target deployment with production adapter
- Produces: reproducible non-live acceptance test and signed-off target checklist

- [ ] **Step 1: Write the complete fake-adapter acceptance flow**

```python
async def test_crm_sync_and_agent_send_acceptance(gateway):
    await gateway.sync.sync_orders()
    await gateway.sync.sync_conversations_and_messages()
    orders = await gateway.crm.get("/v1/orders")
    conversations = await gateway.crm.get("/v1/conversations")
    job = await gateway.agent.post(
        f"/v1/conversations/{conversations.json()['items'][0]['id']}/messages",
        json={"idempotency_key": "acceptance-1", "intent": "greeting", "content": "Hello, thank you for contacting us."},
    )
    await gateway.outbox.run_once()
    final = await gateway.agent.get(f"/v1/jobs/{job.json()['id']}")
    assert orders.json()["items"]
    assert final.json()["state"] == "sent"
```

- [ ] **Step 2: Add negative acceptance cases**

In the same test module, assert a CRM key cannot send, a quote becomes `requires_human_review`, two concurrent identical submissions return one job, login loss pauses work, and an uncertain send receives no second call before reconciliation.

- [ ] **Step 3: Run the full development-machine gate**

Run: `.\.venv\Scripts\python.exe -m pytest -m "not live" --cov=mic_gateway --cov-report=term-missing`

Run: `.\.venv\Scripts\python.exe -m ruff check src tests`

Run: `.\.venv\Scripts\python.exe -m mypy src`

Expected: all non-live tests pass, no lint/type errors, and critical modules `policies/messages.py`, `messaging/outbox.py`, and `api/auth.py` each have at least 90% line coverage.

- [ ] **Step 4: Execute the target-computer gate**

Run database migration, provision three keys, complete dedicated-profile login, run contract tests, run read-only live smoke, run the explicit test-conversation send smoke, start the scheduled task, and verify `/health/live`, `/health/ready`, and authenticated `/v1/status` from the CRM computer context.

- [ ] **Step 5: Exercise restart and operator recovery**

Queue a fake-adapter job in a staging database, stop the process during `sending`, restart, and confirm it becomes `uncertain`. On the live target, log out manually, confirm `operator_action_required`, log back into the dedicated profile, and confirm synchronization resumes without deleting checkpoints.

- [ ] **Step 6: Record acceptance evidence and commit**

Add a dated acceptance section to `docs/operations.md` containing software version, migration revision, non-live test result, contract test result, read-only live result, test-conversation send result, restart result, and operator-recovery result. Record only pass/fail and safe request IDs, never customer data or credentials.

Commit: `git add tests/integration/test_acceptance_flow.py docs/operations.md && git commit -m "test: verify gateway acceptance flow"`

## Final Verification

- [ ] Run: `.\.venv\Scripts\python.exe -m pytest -m "not live" -v`
- [ ] Run: `.\.venv\Scripts\python.exe -m ruff check src tests`
- [ ] Run: `.\.venv\Scripts\python.exe -m mypy src`
- [ ] On the target computer, run: `.\.venv\Scripts\python.exe -m pytest tests/contract tests/live/test_read_only_smoke.py -v --live`
- [ ] With the designated test conversation, run: `.\.venv\Scripts\python.exe -m pytest tests/live/test_send_smoke.py -v --live-send`
- [ ] Verify the scheduled task, Windows firewall rule, dedicated browser profile, key roles, status freshness, restart recovery, and operator login recovery using `docs/operations.md`.
- [ ] Confirm `git status --short` is clean and review the complete branch against the design spec.
