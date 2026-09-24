# Alibaba & MIC Keep-Alive, Auto-Refresh & Live Sync Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement robust session keep-alive, active page refreshing, and continuous live synchronization for both Alibaba (`alibaba-client`) and Made-in-China (`mic-client`) to guarantee the newest conversations and messages are perpetually captured and synced to EspoCRM without session staleness or connection drops.

**Architecture:**
- **Alibaba Client**:
  - Implement `keep_alive(force_reload, max_idle_seconds)` in `AlibabaMessengerBot` to maintain Chromium browser lifecycle, detect session drop/expiration, dismiss transient dialogs, and reload the message center DOM.
  - Enhance `get_recent_conversations(limit, auto_refresh=True)` to actively refresh the page / DOM before extracting inquiries, preventing stale cached DOM reads.
  - Enhance `AlibabaSyncService.run_daemon` with periodic keep-alive heartbeats, automatic error backoff and self-healing reconnection.
  - Add optional in-process background sync worker in `server.py` (controlled via `FUSANHE_AUTO_SYNC=true` or API) plus `/api/health` and `/api/session/keepalive` endpoints.
- **MIC Client**:
  - Enable automatic `.env` loading in `mic_gateway.crm_bridge.config` so bridge daemon runs zero-config.
  - Enhance `MadeInChinaAdapter.check_session` to detect stale DOM / idle connection and force refresh when session health is degraded.
  - Provide unified server runner scripts (`scripts/run_production.py` or `.ps1`) for launching both gateway and bridge daemon with health monitoring.
- **Deployment & Server Readiness**:
  - Provide systemd unit templates and supervisor configs for Linux/Windows server deployment.

**Tech Stack:** Python 3.14 / 3.11+, Playwright, FastAPI, Pydantic, SQLAlchemy, Pytest

**Spec:** User request: "然后确保alibb和mic这些都会保活刷新，以确保同步最新的会话"

## Global Constraints
- `FUSANHE_OUTBOUND_PAUSED=true` must remain enforced across all components; no real outbound messages.
- Privacy: No tokens, passwords, or customer personal info in logs or console output.
- All existing tests in `alibaba-client` (81 tests) and `mic-client` must continue to pass without regression.

## Review Focus
1. Alibaba stale DOM problem: `get_recent_conversations` previously never reloaded the page, leaving DOM frozen. Active refresh must be safe, performant, and wait for dynamic render.
2. Login state loss: When session cookies expire or redirected to login, the keep-alive must detect it immediately and update `is_logged_in=False` instead of hanging or erroring out.
3. Concurrent browser lock: Active reload in background must respect `browser_lock` in `server.py` so API requests don't collide with page reloads.
4. MIC bridge environment loading: Bridge CLI must load `.env` reliably regardless of working directory.
5. Graceful shutdown: Daemons on both platforms must handle SIGINT / SIGTERM cleanly and release browser locks and DB connections.

---

### Task 1: Alibaba Bot Keep-alive & Refresh Mechanism (`alibaba_bot.py`)

**Files:**
- Modify: `alibaba-client/alibaba_messenger/alibaba_bot.py`
- Test: `alibaba-client/tests/test_read_messages.py`

**Interfaces:**
- Consumes: Playwright page, `settings.ALIBABA_MSG_URL`
- Produces: `bot.keep_alive(force_reload=False, max_idle_seconds=180) -> bool`, `bot.get_recent_conversations(limit=20, auto_refresh=True)`

- [ ] **Step 1: Write failing test in `test_read_messages.py`**

```python
@pytest.mark.asyncio
async def test_bot_keep_alive_reloads_when_idle():
    bot_instance = AlibabaMessengerBot()
    bot_instance.is_logged_in = True
    bot_instance.page = AsyncMock()
    bot_instance.page.is_closed = MagicMock(return_value=False)
    bot_instance.page.url = settings.ALIBABA_MSG_URL
    ...
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_read_messages.py -k test_bot_keep_alive -v`
Expected: FAIL

- [ ] **Step 3: Implement `keep_alive` and auto-refresh in `alibaba_bot.py`**
- Track `self._last_refresh_time: float` and `self._last_keep_alive: float`.
- Implement `keep_alive(force_reload=False, max_idle_seconds=180.0) -> bool`.
- In `get_recent_conversations`: add `auto_refresh: bool = False` (default False for backwards test compatibility, True in daemon) which reloads page and waits for DOM render before evaluating script.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_read_messages.py -k test_bot_keep_alive -v`
Expected: PASS

---

### Task 2: Alibaba Sync Service Daemon Self-Healing (`sync_service.py`, `run_sync.py`)

**Files:**
- Modify: `alibaba-client/alibaba_messenger/sync_service.py`
- Modify: `alibaba-client/alibaba_messenger/run_sync.py`
- Test: `alibaba-client/tests/test_sync_service.py`

**Interfaces:**
- Consumes: `bot.keep_alive()`, `bot.get_recent_conversations(auto_refresh=True)`
- Produces: Resilient `run_daemon` with periodic keep-alive and self-healing

- [ ] **Step 1: Write failing test for daemon keep-alive and error resilience in `test_sync_service.py`**

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_sync_service.py -k test_daemon_keep_alive -v`
Expected: FAIL

- [ ] **Step 3: Implement keep-alive and refresh in `sync_service.py` and `run_sync.py`**
- In `run_incremental_once`: pass `auto_refresh=True` to `bot.get_recent_conversations`.
- In `run_daemon`: run `bot.keep_alive()` on every tick, catch exceptions with backoff, recover gracefully.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_sync_service.py -v`
Expected: PASS

---

### Task 3: Alibaba Server Background Auto-Sync & Session Health API (`server.py`)

**Files:**
- Modify: `alibaba-client/alibaba_messenger/server.py`
- Test: `alibaba-client/tests/test_server.py`

**Interfaces:**
- Consumes: `GET /api/health`, `POST /api/session/keepalive`, `POST /api/session/refresh`
- Produces: API responses with live session health and refresh status

- [ ] **Step 1: Write failing tests in `test_server.py`**

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_server.py -k "test_health or test_keepalive" -v`
Expected: FAIL

- [ ] **Step 3: Implement `/api/health`, `/api/session/keepalive`, and `/api/session/refresh` in `server.py`**
- Return detailed status: `{status: "UP", is_logged_in: bool, last_keep_alive: float, page_url: str}`.
- Trigger `bot.keep_alive(force_reload=True)` under `browser_lock`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_server.py -v`
Expected: PASS

---

### Task 4: MIC Client Keep-alive, Auto-Refresh & Environment Loading (`mic-client`)

**Files:**
- Modify: `mic-client/src/mic_gateway/crm_bridge/config.py`
- Modify: `mic-client/src/mic_gateway/adapters/made_in_china/adapter.py`
- Test: `mic-client/tests/`

**Interfaces:**
- Consumes: `mic-client/.env`
- Produces: Auto-loaded configuration and resilient session refresh in `MadeInChinaAdapter`

- [ ] **Step 1: Write test for `.env` auto-loading in `crm_bridge/config.py`**

- [ ] **Step 2: Run test to verify it fails**

- [ ] **Step 3: Implement `.env` auto-loading in `CrmBridgeConfig.from_env` and idle-refresh in `MadeInChinaAdapter`**
- Load `.env` from `mic-client/.env` if present.
- In `MadeInChinaAdapter.check_session`: if page has been on same URL > 5 minutes without reload, force re-navigation to keep WebSocket alive.

- [ ] **Step 4: Run tests to verify they pass**

---

### Task 5: Server Deployment Supervisor & Run Scripts

**Files:**
- Create: `alibaba-client/scripts/run_daemon.py`
- Create: `mic-client/scripts/run_production_daemon.py`
- Create: `docs/SERVER_DEPLOYMENT_KEEP_ALIVE.md`

**Interfaces:**
- Unified startup and keep-alive verification for server deployment

- [ ] **Step 1: Create Alibaba daemon launcher with keep-alive loop**
- [ ] **Step 2: Create MIC production daemon launcher combining gateway & bridge**
- [ ] **Step 3: Write comprehensive deployment guide (`docs/SERVER_DEPLOYMENT_KEEP_ALIVE.md`)**
- [ ] **Step 4: Run full test suites on both projects and verify 100% pass**
- [ ] **Step 5: Commit and push changes to `main`**
