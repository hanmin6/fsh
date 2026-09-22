# Alibaba Message Sync Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Securely import every Alibaba text conversation into CRM with resumable backfill, five-minute incremental sync, idempotent messages, and automatic Lead creation when no reliable customer match exists.

**Architecture:** `alibb` remains the browser-facing transport. It enumerates Alibaba conversations, normalizes history into a stable contract, checkpoints progress in local SQLite, and pushes authenticated batches to one CRM sync endpoint. CRM owns identity resolution, Lead creation, message persistence, final conversation state, and audit records; backfill mode is explicitly side-effect-free with respect to unread counts, AI drafts, and outbound tasks.

**Tech Stack:** Python 3.10+, Playwright, FastAPI/Pydantic, sqlite3, requests, pytest; EspoCRM 10.0.8, PHP 8, MariaDB, Docker Compose, Python unittest runtime tests.

**Repository constraint:** The user explicitly prohibited autonomous `git commit` and `git push`. Every task ends with a diff review checkpoint instead of a commit. Do not stage, commit, tag, or push unless the user later authorizes it.

**Design reference:** `docs/superpowers/specs/2026-09-21-alibaba-messenger-crm-integration-design.md`

---

## File map

### CRM repository: `G:\FSH\CRM\fsh`

- Modify `custom/Espo/Custom/Resources/metadata/entityDefs/AutomationAgent.json`: independent Agent credential metadata.
- Modify `custom/Espo/Custom/Resources/metadata/entityDefs/ExternalConversation.json`: source timestamps and sync status.
- Modify `custom/Espo/Custom/Resources/metadata/entityDefs/ExternalMessage.json`: raw source time, confidence, sequence, and message type.
- Modify `custom/Espo/Custom/Resources/metadata/entityDefs/AutomationAudit.json`: indexed request ID for replay-safe sync writes.
- Modify `custom/Espo/Custom/Tools/Fusanhe/AutomationAuth.php`: bootstrap registration authentication plus per-Agent authentication.
- Modify `custom/Espo/Custom/Tools/Fusanhe/WorkflowService.php`: issue/rotate Agent credentials without changing claim semantics.
- Modify the five existing Agent action classes under `custom/Espo/Custom/Tools/Fusanhe/Api/`: derive `agentKey` from authenticated headers.
- Create `custom/Espo/Custom/Tools/Fusanhe/AlibabaSyncService.php`: validate and transactionally persist one conversation batch.
- Create `custom/Espo/Custom/Tools/Fusanhe/Api/PostAlibabaSync.php`: authenticated sync API action.
- Modify `custom/Espo/Custom/Resources/routes.json`: register `/Fusanhe/alibaba/sync`.
- Create `tests/test_alibaba_sync_contract.py`: offline metadata and source contract tests.
- Create `tests/test_alibaba_sync_runtime.py`: isolated Docker behavioral tests.
- Modify `tests/phase1-compose.yaml`: expose any new non-secret test configuration only.

### Alibaba repository: `G:\FSH\alibb`

- Modify `.gitignore`: ignore `.env`, local SQLite state, Profile, logs, tokens, and screenshots.
- Create `.env.example`: non-secret CRM and sync configuration.
- Modify `alibaba_crm_client.py`: read existing official-API secrets from environment without changing official API behavior.
- Modify `alibaba_messenger/config.py`: load CRM, Agent, account, interval, and state database settings.
- Create `alibaba_messenger/sync_models.py`: normalized conversation/message contracts and deterministic fingerprinting.
- Create `alibaba_messenger/sync_state.py`: SQLite checkpoints and request-result replay state.
- Create `alibaba_messenger/crm_gateway.py`: Agent registration, authentication, and sync batch transport.
- Modify `alibaba_messenger/alibaba_bot.py`: all-page enumeration and enriched history extraction.
- Create `alibaba_messenger/sync_service.py`: backfill and incremental orchestration.
- Create `alibaba_messenger/run_sync.py`: explicit backfill and continuous-sync CLI.
- Create/modify tests under `tests/`: unit and orchestration coverage.
- Modify `alibaba_messenger/README.md`: setup, backfill, incremental operation, recovery, and non-goals.

---

### Task 1: Quarantine credentials and define local configuration

**Files:**
- Modify: `G:\FSH\alibb\.gitignore`
- Create: `G:\FSH\alibb\.env.example`
- Modify: `G:\FSH\alibb\alibaba_crm_client.py:20-34`
- Modify: `G:\FSH\alibb\alibaba_messenger\config.py`
- Test: `G:\FSH\alibb\tests\test_config.py`

- [ ] **Step 1: Extend the failing configuration test**

Add assertions that defaults are safe and secrets are not embedded in source defaults:

```python
def test_crm_sync_defaults_are_safe(monkeypatch, tmp_path):
    for key in (
        "CRM_API_URL", "FUSANHE_AGENT_KEY", "FUSANHE_AGENT_TOKEN",
        "ALIBABA_ACCOUNT_HANDLE", "ALIBABA_SYNC_DB_PATH",
    ):
        monkeypatch.delenv(key, raising=False)

    settings = Settings(BASE_DIR=str(tmp_path))
    assert settings.CRM_API_URL == "http://localhost:8080/api/v1"
    assert settings.AGENT_KEY == "guangzhou-alibaba-01"
    assert settings.AGENT_TOKEN == ""
    assert settings.ACCOUNT_HANDLE == "default"
    assert settings.SYNC_INTERVAL_SECONDS == 300
    assert settings.SYNC_BATCH_SIZE == 100
    assert settings.SYNC_DB_PATH.endswith("alibaba_sync.db")
```

- [ ] **Step 2: Run the targeted test and verify RED**

Run from `G:\FSH\alibb`:

```powershell
python -m pytest tests/test_config.py -v
```

Expected: FAIL because the CRM and sync settings do not exist.

- [ ] **Step 3: Add environment-backed settings**

Implement these fields in `Settings` while keeping existing paths and browser timing fields:

```python
CRM_API_URL: str = os.getenv("CRM_API_URL", "http://localhost:8080/api/v1").rstrip("/")
AGENT_KEY: str = os.getenv("FUSANHE_AGENT_KEY", "guangzhou-alibaba-01")
AGENT_TOKEN: str = os.getenv("FUSANHE_AGENT_TOKEN", "")
ACCOUNT_HANDLE: str = os.getenv("ALIBABA_ACCOUNT_HANDLE", "default")
SYNC_INTERVAL_SECONDS: int = int(os.getenv("ALIBABA_SYNC_INTERVAL_SECONDS", "300"))
SYNC_BATCH_SIZE: int = int(os.getenv("ALIBABA_SYNC_BATCH_SIZE", "100"))
SYNC_DB_PATH: str = os.getenv(
    "ALIBABA_SYNC_DB_PATH",
    os.path.join(BASE_DIR, "data", "alibaba_sync.db"),
)
```

Extend `ensure_dirs()` with `os.makedirs(os.path.dirname(self.SYNC_DB_PATH), exist_ok=True)`.

- [ ] **Step 4: Remove official API credentials from Python literals**

Keep the existing `AlibabaCRMClient` behavior but replace literal application configuration with environment reads:

```python
APP_KEY = os.getenv("ALIBABA_APP_KEY", "")
APP_SECRET = os.getenv("ALIBABA_APP_SECRET", "")
REDIRECT_URI = os.getenv(
    "ALIBABA_REDIRECT_URI",
    "https://api.fsh.digital/alibaba/oauth/callback",
)

class AlibabaCRMClient:
    def __init__(self, app_key: str = APP_KEY, app_secret: str = APP_SECRET):
        if not app_key or not app_secret:
            raise ValueError("ALIBABA_APP_KEY and ALIBABA_APP_SECRET are required")
        self.app_key = app_key
        self.app_secret = app_secret
        self.token_info = self._load_token()
```

Do not change the callback URL flow, token exchange, official endpoint list, or signing algorithm.

- [ ] **Step 5: Create a non-secret `.env.example` and harden ignores**

The example file must contain names and safe defaults only:

```dotenv
CRM_API_URL=http://localhost:8080/api/v1
FUSANHE_AGENT_KEY=guangzhou-alibaba-01
FUSANHE_AGENT_TOKEN=
ALIBABA_ACCOUNT_HANDLE=default
ALIBABA_SYNC_INTERVAL_SECONDS=300
ALIBABA_SYNC_BATCH_SIZE=100
ALIBABA_SYNC_DB_PATH=alibaba_messenger/data/alibaba_sync.db
ALIBABA_APP_KEY=
ALIBABA_APP_SECRET=
ALIBABA_REDIRECT_URI=https://api.fsh.digital/alibaba/oauth/callback
```

Ensure `.gitignore` contains:

```gitignore
.env
.env.*
!.env.example
token_storage.json
alibaba_messenger/data/
alibaba_messenger/profile/
alibaba_messenger/logs/
```

- [ ] **Step 6: Run tests and secret-name scan**

```powershell
python -m pytest tests/test_config.py -v
rg -n "APP_SECRET\s*=\s*[\"'][^\"']+[\"']|ACCESS_TOKEN\s*=\s*[\"'][^\"']+[\"']" -g '*.py' -g '!iop-sdk-python-1.0.2/test/**'
```

Expected: tests PASS; scan returns no application secret or access token literal in maintained source. The vendored SDK demo remains excluded from the future initial commit unless its sample credentials are sanitized.

- [ ] **Step 7: Review checkpoint**

Run `git status --short` in `G:\FSH\alibb`. Confirm no token, Profile, log, screenshot, SQLite, or `.env` file appears as trackable. Do not commit.

---

### Task 2: Add independent Agent credentials to CRM

**Files:**
- Modify: `custom/Espo/Custom/Resources/metadata/entityDefs/AutomationAgent.json`
- Modify: `custom/Espo/Custom/Tools/Fusanhe/AutomationAuth.php`
- Modify: `custom/Espo/Custom/Tools/Fusanhe/WorkflowService.php:369-410`
- Modify: `custom/Espo/Custom/Tools/Fusanhe/Api/PostAgentRegister.php`
- Modify: `custom/Espo/Custom/Tools/Fusanhe/Api/PostAgentHeartbeat.php`
- Modify: `custom/Espo/Custom/Tools/Fusanhe/Api/PostAgentClaim.php`
- Modify: `custom/Espo/Custom/Tools/Fusanhe/Api/PostTaskSending.php`
- Modify: `custom/Espo/Custom/Tools/Fusanhe/Api/PostTaskResult.php`
- Test: `tests/test_alibaba_sync_contract.py`

- [ ] **Step 1: Write offline contract tests for credential metadata and auth methods**

Create `tests/test_alibaba_sync_contract.py` with:

```python
import json
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]

class AgentCredentialContract(unittest.TestCase):
    def test_agent_has_independent_credential_fields(self):
        data = json.loads((ROOT / "custom/Espo/Custom/Resources/metadata/entityDefs/AutomationAgent.json").read_text(encoding="utf-8"))
        fields = data["fields"]
        self.assertIn("credentialHash", fields)
        self.assertTrue(fields["credentialHash"]["readOnly"])
        self.assertEqual(fields["credentialStatus"]["options"], ["active", "revoked"])
        self.assertIn("lastCredentialUsedAt", fields)
        self.assertIn("clientVersion", fields)

    def test_auth_separates_bootstrap_and_agent_tokens(self):
        source = (ROOT / "custom/Espo/Custom/Tools/Fusanhe/AutomationAuth.php").read_text(encoding="utf-8")
        self.assertIn("assertBootstrap", source)
        self.assertIn("assertAgent", source)
        self.assertIn("X-Agent-Key", source)
        self.assertIn("X-Agent-Token", source)
        self.assertIn("password_verify", source)
```

- [ ] **Step 2: Run the tests and verify RED**

```powershell
$env:PYTHONUTF8='1'; python -m unittest tests.test_alibaba_sync_contract.AgentCredentialContract -v
```

Expected: FAIL for missing fields and methods.

- [ ] **Step 3: Add credential metadata**

Add these fields to `AutomationAgent.json`:

```json
"credentialHash": {
  "type": "varchar",
  "maxLength": 255,
  "readOnly": true,
  "layoutListDisabled": true,
  "layoutMassUpdateDisabled": true
},
"credentialStatus": {
  "type": "enum",
  "options": ["active", "revoked"],
  "default": "active",
  "displayAsLabel": true
},
"lastCredentialUsedAt": {"type": "datetime", "readOnly": true},
"clientVersion": {"type": "varchar", "maxLength": 100}
```

- [ ] **Step 4: Split bootstrap and Agent authentication**

Implement `AutomationAuth` with these public contracts:

```php
public function assertBootstrap(Request $request): void;
public function assertAgent(Request $request): Entity;
```

`assertBootstrap` retains the existing constant-time `FUSANHE_AUTOMATION_TOKEN` check and is used only for registration or explicit credential rotation.

`assertAgent` must:

```php
$key = trim((string) ($request->getHeader('X-Agent-Key') ?? ''));
$token = (string) ($request->getHeader('X-Agent-Token') ?? '');
$agent = $this->em->getRDBRepository('AutomationAgent')->where(['agentKey' => $key])->findOne();
if (!$agent || $agent->get('credentialStatus') !== 'active') {
    throw new Forbidden('Invalid agent credential.');
}
if ($token === '' || !password_verify($token, (string) $agent->get('credentialHash'))) {
    throw new Forbidden('Invalid agent credential.');
}
$agent->set('lastCredentialUsedAt', gmdate('Y-m-d H:i:s'));
$this->kernel->save($agent);
return $agent;
```

Inject `EntityManager` and `ServiceKernel` into the class constructor.

- [ ] **Step 5: Issue a token once during registration**

Change registration so bootstrap authentication occurs in `PostAgentRegister`. Pass `rotateCredential` into `WorkflowService::registerAgent`. On first registration or explicit rotation:

```php
$secret = rtrim(strtr(base64_encode(random_bytes(32)), '+/', '-_'), '=');
$agent->set([
    'credentialHash' => password_hash($secret, PASSWORD_ARGON2ID),
    'credentialStatus' => 'active',
]);
```

Return `agentToken` only in that response and never store the plaintext. Existing registration responses without issue/rotation return `credentialIssued: false` and omit `agentToken`.

- [ ] **Step 6: Derive agent identity from headers in all Agent actions**

For heartbeat, claim, sending, and result actions:

```php
$agent = $this->auth->assertAgent($request);
$body = $request->getParsedBody();
$body->agentKey = (string) $agent->get('agentKey');
```

Never trust a body-provided `agentKey`. Keep existing WorkflowService ownership and capability checks.

- [ ] **Step 7: Run offline tests and PHP lint**

```powershell
$env:PYTHONUTF8='1'; python -m unittest tests.test_alibaba_sync_contract.AgentCredentialContract -v
docker compose exec -T espocrm php -l custom/Espo/Custom/Tools/Fusanhe/AutomationAuth.php
```

Expected: contract tests PASS; PHP reports no syntax errors. If the Docker stack is not running, run PHP lint inside the isolated test stack during Task 5 instead of claiming completion.

- [ ] **Step 8: Review checkpoint**

Inspect `git diff --check` and `git diff`. Verify no plaintext Agent token appears in metadata, source, test fixtures, or logs. Do not commit.

---

### Task 3: Define CRM sync metadata and route contract

**Files:**
- Modify: `custom/Espo/Custom/Resources/metadata/entityDefs/ExternalConversation.json`
- Modify: `custom/Espo/Custom/Resources/metadata/entityDefs/ExternalMessage.json`
- Modify: `custom/Espo/Custom/Resources/routes.json`
- Create: `custom/Espo/Custom/Tools/Fusanhe/Api/PostAlibabaSync.php`
- Extend: `tests/test_alibaba_sync_contract.py`

- [ ] **Step 1: Add failing metadata and route tests**

```python
class AlibabaSyncMetadataContract(unittest.TestCase):
    def entity(self, name):
        return json.loads((ROOT / f"custom/Espo/Custom/Resources/metadata/entityDefs/{name}.json").read_text(encoding="utf-8"))

    def test_sync_fields_exist(self):
        conv = self.entity("ExternalConversation")["fields"]
        for name in ("sourceCreatedAtRaw", "sourceUpdatedAtRaw", "lastSourceSyncAt", "backfillCompletedAt", "syncError"):
            self.assertIn(name, conv)
        msg = self.entity("ExternalMessage")["fields"]
        self.assertEqual(msg["timestampConfidence"]["options"], ["high", "medium", "low"])
        self.assertEqual(msg["messageType"]["options"], ["initialInquiry", "chat"])
        self.assertIn("sourceTimestampRaw", msg)
        self.assertIn("sourceSequence", msg)
        audit = self.entity("AutomationAudit")
        self.assertIn("requestId", audit["fields"])
        self.assertTrue(audit["indexes"]["requestId"]["unique"])

    def test_alibaba_sync_route_is_agent_authenticated(self):
        routes = json.loads((ROOT / "custom/Espo/Custom/Resources/routes.json").read_text(encoding="utf-8"))
        route = next(r for r in routes if r["route"] == "/Fusanhe/alibaba/sync")
        self.assertEqual(route["method"], "post")
        self.assertTrue(route["noAuth"])
        action = ROOT / "custom/Espo/Custom/Tools/Fusanhe/Api/PostAlibabaSync.php"
        source = action.read_text(encoding="utf-8")
        self.assertIn("assertAgent", source)
        self.assertIn("AlibabaSyncService", source)
```

- [ ] **Step 2: Run and verify RED**

```powershell
$env:PYTHONUTF8='1'; python -m unittest tests.test_alibaba_sync_contract.AlibabaSyncMetadataContract -v
```

Expected: FAIL because fields, route, and action are absent.

- [ ] **Step 3: Add fields exactly as approved in the design**

Use varchar fields for raw source values, datetime fields for normalized sync markers, an int for sequence, and enums for confidence/type. Mark synchronization diagnostics read-only and hide long/raw fields from list and mass-update layouts. Add nullable `AutomationAudit.requestId` as a 64-character read-only varchar with a unique index so replay lookup does not depend on querying nested JSON.

- [ ] **Step 4: Add the route**

Append this JSON route object without changing existing route order or semantics:

```json
{
  "route": "/Fusanhe/alibaba/sync",
  "method": "post",
  "actionClassName": "Espo\\Custom\\Tools\\Fusanhe\\Api\\PostAlibabaSync",
  "noAuth": true
}
```

- [ ] **Step 5: Create the action**

```php
<?php
namespace Espo\Custom\Tools\Fusanhe\Api;

use Espo\Core\Api\Action;
use Espo\Core\Api\Request;
use Espo\Core\Api\Response;
use Espo\Core\Api\ResponseComposer;
use Espo\Custom\Tools\Fusanhe\AlibabaSyncService;
use Espo\Custom\Tools\Fusanhe\AutomationAuth;

final class PostAlibabaSync implements Action
{
    public function __construct(
        private AlibabaSyncService $service,
        private AutomationAuth $auth,
    ) {}

    public function process(Request $request): Response
    {
        $agent = $this->auth->assertAgent($request);
        return ResponseComposer::json(
            $this->service->sync($request->getParsedBody(), $agent)
        );
    }
}
```

- [ ] **Step 6: Run contracts and JSON validation**

```powershell
$env:PYTHONUTF8='1'; python -m unittest tests.test_alibaba_sync_contract.AlibabaSyncMetadataContract tests.test_contracts.Contracts.test_all_metadata_is_valid_json -v
```

Expected: PASS.

- [ ] **Step 7: Review checkpoint**

Run `git diff --check`; inspect metadata diff for accidental removal of existing options or indexes. Do not commit.

---

### Task 4: Implement transactional CRM Alibaba sync

**Files:**
- Create: `custom/Espo/Custom/Tools/Fusanhe/AlibabaSyncService.php`
- Modify: `custom/Espo/Custom/Tools/Fusanhe/IdentityService.php`
- Extend: `tests/test_alibaba_sync_contract.py`

- [ ] **Step 1: Write service contract tests before implementation**

Add source-level assertions for required invariants:

```python
class AlibabaSyncServiceContract(unittest.TestCase):
    def test_service_has_backfill_and_incremental_guards(self):
        source = (ROOT / "custom/Espo/Custom/Tools/Fusanhe/AlibabaSyncService.php").read_text(encoding="utf-8")
        for token in (
            "syncMode", "backfill", "incremental", "requestId",
            "finalBatch", "sourceSequence", "timestampConfidence",
            "resolveAutomaticCustomer", "ensureLeadForIdentity", "AutomationAudit",
        ):
            self.assertIn(token, source)
        self.assertIn("getTransactionManager", source)
        self.assertNotIn("generateDraft", source)
        self.assertNotIn("OutboundTask", source)

    def test_identity_service_supports_system_lead_creation(self):
        source = (ROOT / "custom/Espo/Custom/Tools/Fusanhe/IdentityService.php").read_text(encoding="utf-8")
        self.assertIn("ensureLeadForIdentity", source)
        self.assertIn("resolveAutomaticCustomer", source)
        self.assertIn("source' => 'Web Site'", source)
        self.assertIn("来源：Alibaba", source)
```

- [ ] **Step 2: Run and verify RED**

```powershell
$env:PYTHONUTF8='1'; python -m unittest tests.test_alibaba_sync_contract.AlibabaSyncServiceContract -v
```

Expected: FAIL because the service and helper are absent.

- [ ] **Step 3: Add deterministic automatic matching and Lead creation helpers**

Add `resolveAutomaticCustomer(Entity $identity, string $conversationExternalId): array`. If the identity is already confirmed, return its existing Account, Contact, or Lead. Otherwise query Account, Contact, and Lead using exact email and/or normalized phone evidence, deduplicate by type and ID, and link automatically only when exactly one candidate exists. Zero or multiple candidates call `ensureLeadForIdentity`, preventing name/country-only merges.

Add `ensureLeadForIdentity`:

```php
public function ensureLeadForIdentity(Entity $identity, string $conversationExternalId): Entity
{
    if ($identity->get('leadId')) {
        $lead = $this->em->getEntityById('Lead', (string) $identity->get('leadId'));
        if ($lead) return $lead;
    }
    $displayName = trim((string) ($identity->get('displayName') ?: $identity->get('name')));
    if ($displayName === '') throw new Conflict('Alibaba identity has no display name.');
    $lead = $this->em->getNewEntity('Lead');
    $lead->set([
        'lastName' => $displayName,
        'status' => 'New',
        'source' => 'Web Site',
        'emailAddress' => (string) $identity->get('emailAddress'),
        'phoneNumber' => (string) $identity->get('phoneNumber'),
        'addressCountry' => (string) $identity->get('country'),
        'description' => '来源：Alibaba；询价单：' . $conversationExternalId . '；身份：' . $identity->get('identityKey'),
    ]);
    $this->kernel->save($lead);
    $identity->set([
        'leadId' => $lead->getId(),
        'linkStatus' => 'confirmed',
        'confirmedAt' => gmdate('Y-m-d H:i:s'),
    ]);
    $this->kernel->save($identity);
    return $lead;
}
```

`resolveAutomaticCustomer` returns:

```php
return [
    'targetType' => $targetType,
    'targetId' => $target->getId(),
    'createdLead' => $createdLead,
    'matchMethod' => $matchMethod,
];
```

Do not call the user-ACL path `createCustomer`; these helpers are only called by the authenticated Alibaba sync service. The sync service records whether the result was `existingConfirmed`, `uniqueEmail`, `uniquePhone`, `newLead`, or `ambiguousNewLead`.

- [ ] **Step 4: Implement `AlibabaSyncService::sync` validation**

Reject with `BadRequest` unless all conditions hold:

- Agent capability contains `Alibaba`.
- `requestId`, `jobId`, `syncMode`, `accountHandle`, and conversation `inquiryId` are non-empty.
- `syncMode` is `backfill` or `incremental`.
- `messages` is an array with at most 100 entries.
- Every message has `externalId`, valid `direction` (`inbound` or `outbound`), non-empty `body`, valid confidence/type, and integer sequence.
- A normalized `sentAt` is present for `high`/`medium`; `low` may fall back to the conversation source time and must retain `sourceTimestampRaw`.
- Request body and individual message lengths stay within explicit constants.

Define constants in the class:

```php
private const MAX_MESSAGES = 100;
private const MAX_BODY_BYTES = 200_000;
private const MAX_BATCH_BYTES = 2_000_000;
```

- [ ] **Step 5: Implement idempotent transactional persistence**

Inside one database transaction:

1. Return the stored prior result if `AutomationAudit.requestId` already contains the same `requestId`.
2. Find/create `ExternalChannel` with type Alibaba and matching `accountHandle`; reject disabled channels.
3. Find/create `ExternalConversation` by `channelId + inquiryId`.
4. Resolve `ExternalIdentity` using buyer external ID when available, otherwise the existing anonymous-per-inquiry key.
5. Call `resolveAutomaticCustomer`; attach the unique strong match, or create one idempotent Lead when the match is missing or ambiguous.
6. Insert each new `ExternalMessage` using `conversationId + contentHash` and `externalId` checks; preserve direction and mark historical outbound as `sent`.
7. In backfill mode, do not increment unread, generate drafts, create tasks, or change state until `finalBatch=true`.
8. On the final batch or in incremental mode, set status from the newest valid direction, use the source unread count, and update source timestamps.
9. Write one `alibaba.sync.request` audit with the indexed `requestId`, mode, counts, match method, and no message bodies.
10. Commit and return stable counts.

Response shape:

```php
return [
    'requestId' => $requestId,
    'conversationId' => $conversation->getId(),
    'identityId' => $identity->getId(),
    'leadId' => $conversation->get('leadId'),
    'createdConversation' => $createdConversation,
    'createdLead' => $createdLead,
    'createdMessages' => $createdMessages,
    'deduplicatedMessages' => $deduplicatedMessages,
    'finalized' => $finalBatch || $syncMode === 'incremental',
];
```

- [ ] **Step 6: Run contracts and PHP lint**

```powershell
$env:PYTHONUTF8='1'; python -m unittest tests.test_alibaba_sync_contract -v
docker compose exec -T espocrm sh -lc 'php -l custom/Espo/Custom/Tools/Fusanhe/AlibabaSyncService.php && php -l custom/Espo/Custom/Tools/Fusanhe/IdentityService.php'
```

Expected: all offline contracts PASS and PHP lint reports no syntax errors.

- [ ] **Step 7: Review checkpoint**

Check that backfill source contains no call to AI generation or OutboundTask creation, audit details exclude body/raw payload, and transaction rollback wraps all persistence. Do not commit.

---

### Task 5: Prove CRM sync behavior in an isolated runtime stack

**Files:**
- Create: `tests/test_alibaba_sync_runtime.py`
- Modify: `tests/phase1-compose.yaml`

- [ ] **Step 1: Write runtime helpers and registration setup**

Use the existing `api`, `admin_api`, and isolated-stack pattern from `test_phase1_runtime.py`. Register an Alibaba-capable real Agent with the bootstrap token, capture the one-time token, and construct:

```python
agent_headers = {
    "X-Agent-Key": agent_key,
    "X-Agent-Token": agent_token,
    "Content-Type": "application/json",
}
```

Do not print `agent_token`.

- [ ] **Step 2: Add failing backfill behavior tests**

Test a two-batch conversation containing initial inquiry, buyer chat, seller chat, and a duplicate message. Assert:

- First batch creates conversation, identity, Lead, and messages.
- Replaying its `requestId` returns the same counts.
- Non-final backfill leaves unread/status side effects unfinalized.
- Final batch produces exactly one conversation, one Lead, and the unique message count.
- Last seller message sets `replied`; source unread count is preserved.
- No AIReplyDraft or OutboundTask exists for the conversation.

- [ ] **Step 3: Add failing incremental behavior tests**

Push a new inbound message with a new request ID. Assert status becomes `pending`, unread uses the supplied source value, and duplicate replay adds nothing. Push a later outbound historical message and assert status becomes `replied` without creating a task.

- [ ] **Step 4: Add authentication tests**

Assert 403 for missing headers, wrong token, revoked credential, or an Agent without Alibaba capability. Assert a body `agentKey` cannot impersonate another Agent because header identity wins.

- [ ] **Step 5: Start the isolated stack and rebuild**

```powershell
docker compose -p fusanhe-alibaba-sync-test --env-file .env.test -f tests/phase1-compose.yaml up -d --wait
docker compose -p fusanhe-alibaba-sync-test --env-file .env.test -f tests/phase1-compose.yaml exec -T espocrm bin/command rebuild
```

Expected: database and EspoCRM services healthy; rebuild succeeds.

- [ ] **Step 6: Run runtime tests**

```powershell
$env:ESPOCRM_API_URL='http://localhost:18080/api/v1'
$env:ESPOCRM_ADMIN_USERNAME='admin'
$env:ESPOCRM_ADMIN_PASSWORD='phase1-test-admin-password'
$env:FUSANHE_AUTOMATION_TOKEN='phase1-test-automation-token-0123456789abcdef'
$env:PYTHONUTF8='1'
python -m unittest tests.test_alibaba_sync_runtime -v
```

Expected: all Alibaba sync runtime tests PASS.

- [ ] **Step 7: Run CRM regression suites**

```powershell
$env:PYTHONUTF8='1'; python -m unittest tests.test_contracts tests.test_phase1 tests.test_p0_fixes -v
```

Update existing runtime tests to register and use per-Agent headers where the shared token previously authenticated claim/sending/result. Expected: no regression in identity, pause, human takeover, snapshot, or receipt behavior.

- [ ] **Step 8: Review checkpoint**

Run `git status --short`, `git diff --check`, and review the runtime database only through test assertions. Do not commit or tear down unrelated Docker projects.

---

### Task 6: Define normalized Python sync models and fingerprints

**Files:**
- Create: `G:\FSH\alibb\alibaba_messenger\sync_models.py`
- Create: `G:\FSH\alibb\tests\test_sync_models.py`

- [ ] **Step 1: Write failing normalization tests**

```python
from alibaba_messenger.sync_models import ConversationSnapshot, SyncMessage

def test_message_fingerprint_is_stable():
    first = SyncMessage.from_source(
        inquiry_id="13907077489", sender="buyer", content="  Hello\r\nworld  ",
        translation="", raw_time="2026-09-21 11:24", sequence=2,
        platform_id=None, message_type="chat",
    )
    second = SyncMessage.from_source(
        inquiry_id="13907077489", sender="buyer", content="Hello\nworld",
        translation="", raw_time="2026-09-21 11:24", sequence=2,
        platform_id=None, message_type="chat",
    )
    assert first.external_id == second.external_id
    assert first.direction == "inbound"
    assert first.body == "Hello\nworld"

def test_system_message_is_not_constructed():
    assert SyncMessage.from_source(
        inquiry_id="1", sender="system", content="assigned", translation="",
        raw_time="11:24", sequence=1, platform_id=None, message_type="chat",
    ) is None
```

- [ ] **Step 2: Run and verify RED**

```powershell
python -m pytest tests/test_sync_models.py -v
```

Expected: FAIL because `sync_models` does not exist.

- [ ] **Step 3: Implement immutable Pydantic models**

Define `SyncMessage` and `ConversationSnapshot` with `extra='forbid'`. `from_source` must:

- Return `None` for system messages.
- Map buyer to inbound and seller to outbound.
- Normalize CRLF and surrounding whitespace without altering internal wording.
- Use platform ID when present; otherwise SHA-256 the canonical JSON array `[inquiryId, direction, rawTime, normalizedBody, sequence]`.
- Classify full datetime as high confidence, date-only as medium, and time-only/unknown as low.
- Preserve the original source time.

Use Python snake-case attributes with explicit CRM aliases:

```python
class SyncMessage(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    external_id: str = Field(alias="externalId")
    direction: Literal["inbound", "outbound"]
    body: str
    translated_body: str = Field(default="", alias="translatedBody")
    sent_at: str | None = Field(default=None, alias="sentAt")
    source_timestamp_raw: str = Field(alias="sourceTimestampRaw")
    timestamp_confidence: Literal["high", "medium", "low"] = Field(alias="timestampConfidence")
    source_sequence: int = Field(alias="sourceSequence", ge=1)
    message_type: Literal["initialInquiry", "chat"] = Field(alias="messageType")
```

Use this exact fingerprint implementation:

```python
raw = json.dumps(
    [inquiry_id, direction, raw_time.strip(), body, int(sequence)],
    ensure_ascii=False,
    separators=(",", ":"),
)
external_id = platform_id or "sha256:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()
```

- [ ] **Step 4: Run tests**

```powershell
python -m pytest tests/test_sync_models.py -v
```

Expected: PASS.

- [ ] **Step 5: Review checkpoint**

Ensure models contain no browser objects, settings globals, HTTP code, or file writes. Do not commit.

---

### Task 7: Enumerate every conversation and enrich history extraction

**Files:**
- Modify: `G:\FSH\alibb\alibaba_messenger\alibaba_bot.py`
- Modify: `G:\FSH\alibb\tests\test_read_messages.py`

- [ ] **Step 1: Add failing pagination tests**

Mock page extraction for three pages where page 3 is empty. Test a new method:

```python
result = await bot_instance.get_all_conversations()
assert [c["inquiry_id"] for c in result] == ["100", "101", "102"]
assert mock_page.goto.await_count <= 3
```

Add a repeated-page fixture and assert the method stops rather than looping forever.

- [ ] **Step 2: Add failing enriched-history tests**

Extend the extracted fixture with `platform_id`, date separators, system messages, translations, and duplicate-looking same-text messages. Assert output:

- Contains only initial inquiry, buyer, and seller messages.
- Carries platform IDs where present.
- Assigns stable source sequence after chronological normalization.
- Combines nearest date separator with time-only messages.
- Marks unresolved time-only values as low confidence.

- [ ] **Step 3: Run targeted tests and verify RED**

```powershell
python -m pytest tests/test_read_messages.py -v
```

Expected: FAIL for absent all-page API and absent enriched fields.

- [ ] **Step 4: Extract reusable current-page parsing**

Move the existing DOM evaluation body into a private `_read_conversation_page()` method returning raw dictionaries. Keep selectors and existing public `/api/conversations` behavior backward compatible.

- [ ] **Step 5: Implement bounded pagination**

Add:

```python
async def get_all_conversations(self, max_pages: int = 10_000) -> list[dict]:
```

For each page, compute a tuple of inquiry IDs. Stop when the page is empty, the tuple has appeared before, no next-page control exists, or `max_pages` is reached. Raise a typed extraction error if `max_pages` is exhausted so a broken page never silently truncates the backfill.

- [ ] **Step 6: Enrich `_extract_dialogue_messages`**

The DOM script must capture stable data attributes (`data-id`, `data-message-id`, `id`) before using a fingerprint, collect date separators in DOM order, and return `sender`, `content`, `translation`, `raw_time`, `platform_id`, and `message_type`. Convert raw dictionaries through `SyncMessage.from_source` after chronological normalization.

Expose two sync-facing methods without changing the existing FastAPI response methods:

```python
async def get_sync_history(self, inquiry_id: str) -> list[SyncMessage]:
    result = await self.get_chat_history(inquiry_id=inquiry_id, limit=0, order="asc")
    if not result["success"]:
        raise RuntimeError(result["status"])
    return [
        message for sequence, raw in enumerate(result["data"]["messages"], start=1)
        if (message := SyncMessage.from_source(
            inquiry_id=inquiry_id,
            sender=raw["sender"],
            content=raw["content"],
            translation=raw.get("translation", ""),
            raw_time=raw.get("raw_time") or raw.get("time", ""),
            sequence=sequence,
            platform_id=raw.get("platform_id"),
            message_type=raw.get("type", "chat"),
        )) is not None
    ]

async def get_changed_conversations(self, since: str | None) -> list[dict]:
    conversations = await self.get_all_conversations()
    if since is None:
        return conversations
    return [
        item for item in conversations
        if item.get("has_unread")
        or not item.get("last_time")
        or normalize_source_time(item["last_time"]) >= since
    ]
```

`normalize_source_time` must return an ISO-comparable UTC string when a full source date is available and an empty string otherwise; unknown timestamps are included rather than silently skipped.

- [ ] **Step 7: Run read-message regression tests**

```powershell
python -m pytest tests/test_read_messages.py tests/test_mock_bot.py -v
```

Expected: PASS; legacy `get_recent_conversations` and `get_chat_history` response contracts remain valid.

- [ ] **Step 8: Review checkpoint**

Inspect for unbounded loops, sleeps inside unit tests, selectors that expose cookies, and output containing full DOM HTML. Do not commit.

---

### Task 8: Add resumable SQLite sync state

**Files:**
- Create: `G:\FSH\alibb\alibaba_messenger\sync_state.py`
- Create: `G:\FSH\alibb\tests\test_sync_state.py`

- [ ] **Step 1: Write failing lifecycle tests**

Use `tmp_path` to verify:

```python
store = SyncStateStore(tmp_path / "sync.db")
job = store.start_job("backfill", "default")
store.mark_conversation_started(job, "139")
store.record_batch(job, "139", 1, "req-1", {"createdMessages": 100})
store.mark_conversation_complete(job, "139")
assert store.resume_point(job).completed_inquiries == {"139"}
assert store.get_request_result("req-1")["createdMessages"] == 100
```

Open a second store instance and assert persistence survives process restart.

- [ ] **Step 2: Run and verify RED**

```powershell
python -m pytest tests/test_sync_state.py -v
```

- [ ] **Step 3: Implement schema and transaction methods**

Create tables `sync_job`, `conversation_checkpoint`, and `request_result`. Enable WAL and foreign keys. Every public write uses `with self.connection:`. Store only identifiers, counts, hashes, timestamps, modes, and errors; do not store message bodies.

Required methods:

```python
start_job(mode, account_handle) -> str
get_or_create_active_job(mode, account_handle) -> str
mark_conversation_started(job_id, inquiry_id) -> None
record_batch(job_id, inquiry_id, batch_no, request_id, result) -> None
mark_conversation_complete(job_id, inquiry_id) -> None
mark_conversation_failed(job_id, inquiry_id, error_code, error_message) -> None
resume_point(job_id) -> ResumePoint
get_request_result(request_id) -> dict | None
last_success_at() -> str | None
complete_job(job_id) -> None
```

- [ ] **Step 4: Run tests and inspect the database contract**

```powershell
python -m pytest tests/test_sync_state.py -v
```

Expected: PASS; test database contains no column named body, content, cookie, token, or html.

- [ ] **Step 5: Review checkpoint**

Confirm the real database path is ignored by Git and database connections close cleanly. Do not commit.

---

### Task 9: Implement the authenticated CRM gateway

**Files:**
- Create: `G:\FSH\alibb\alibaba_messenger\crm_gateway.py`
- Create: `G:\FSH\alibb\tests\test_crm_gateway.py`

- [ ] **Step 1: Write failing HTTP contract tests**

Mock `requests.Session.request` and verify:

- Registration uses only `X-Automation-Token` and captures the one-time Agent token without logging it.
- Sync uses `X-Agent-Key`, `X-Agent-Token`, `Content-Type`, and `X-Request-Id`.
- 400/403/409 are returned as typed permanent errors.
- 429/500/502/503/504 and network timeouts are typed transient errors.
- A repeated request uses the same request ID and payload.

- [ ] **Step 2: Run and verify RED**

```powershell
python -m pytest tests/test_crm_gateway.py -v
```

- [ ] **Step 3: Implement gateway errors and redacted logging**

Define `CrmPermanentError`, `CrmTransientError`, and `CrmAuthError`. Error messages may contain HTTP status, stable CRM error code, and request ID, but never headers, tokens, or full message bodies.

Use one decoder for every response:

```python
def _decode(self, response, request_id: str) -> dict:
    try:
        data = response.json()
    except ValueError as exc:
        raise CrmTransientError(f"CRM returned non-JSON response; requestId={request_id}") from exc
    if response.status_code in (401, 403):
        raise CrmAuthError(f"CRM authentication failed; requestId={request_id}")
    if response.status_code in (400, 404, 409, 413, 422):
        code = str(data.get("code") or data.get("error") or response.status_code)
        raise CrmPermanentError(f"CRM rejected request: {code}; requestId={request_id}")
    if response.status_code == 429 or response.status_code >= 500:
        raise CrmTransientError(f"CRM unavailable: {response.status_code}; requestId={request_id}")
    response.raise_for_status()
    return data
```

- [ ] **Step 4: Implement registration and sync calls**

```python
class CrmGateway:
    def register(self, bootstrap_token: str, rotate: bool = False) -> str:
        response = self.session.post(
            f"{self.base_url}/Fusanhe/agent/register",
            json={
                "agentKey": self.agent_key,
                "name": "Guangzhou Alibaba Agent",
                "mode": "real",
                "capabilities": ["Alibaba"],
                "rotateCredential": rotate,
            },
            headers={"X-Automation-Token": bootstrap_token},
            timeout=(5, 30),
        )
        data = self._decode(response, response.headers.get("X-Request-Id", "register"))
        token = str(data.get("agentToken") or "")
        if not token:
            raise CrmPermanentError("CRM did not issue an agent token")
        return token

    def sync_batch(self, payload: dict, request_id: str) -> dict:
        response = self.session.post(
            f"{self.base_url}/Fusanhe/alibaba/sync",
            json=payload,
            headers={
                "X-Agent-Key": self.agent_key,
                "X-Agent-Token": self.agent_token,
                "X-Request-Id": request_id,
                "Content-Type": "application/json",
            },
            timeout=(5, 30),
        )
        return self._decode(response, request_id)
```

Use a `requests.Session`, explicit connect/read timeouts `(5, 30)`, and no automatic retry inside `sync_batch`; orchestration owns retry timing so SQLite checkpoints and request IDs remain consistent.

- [ ] **Step 5: Run tests**

```powershell
python -m pytest tests/test_crm_gateway.py -v
```

Expected: PASS.

- [ ] **Step 6: Review checkpoint**

Search test output and source for printed tokens. Confirm TLS verification is never disabled. Do not commit.

---

### Task 10: Orchestrate backfill and five-minute incremental sync

**Files:**
- Create: `G:\FSH\alibb\alibaba_messenger\sync_service.py`
- Create: `G:\FSH\alibb\alibaba_messenger\run_sync.py`
- Create: `G:\FSH\alibb\tests\test_sync_service.py`
- Modify: `G:\FSH\alibb\tests\test_runner_cli.py`

- [ ] **Step 1: Write failing backfill orchestration tests**

With fake bot, gateway, and store, assert:

- Every conversation is processed in page order.
- Histories split into batches of 100.
- Only the final batch has `finalBatch=true`.
- The checkpoint advances only after CRM success.
- Permanent failure marks one conversation failed and continues.
- Transient failure retries with the same request ID, then preserves the checkpoint if exhausted.
- Already completed inquiries are skipped after restart.

- [ ] **Step 2: Write failing incremental tests**

Assert only new/updated/unread conversations are refreshed; unchanged fingerprints are skipped; polling sleeps for exactly configured interval through an injected sleeper; login-related bot errors stop the cycle without discarding checkpoints.

- [ ] **Step 3: Run and verify RED**

```powershell
python -m pytest tests/test_sync_service.py tests/test_runner_cli.py -v
```

- [ ] **Step 4: Implement `AlibabaSyncService`**

Constructor dependencies:

```python
from dataclasses import dataclass
import asyncio
import hashlib
import json
import uuid

@dataclass
class SyncSummary:
    job_id: str
    mode: str
    completed: int = 0
    failed: int = 0
    skipped: int = 0

def chunked(items, size):
    return [items[index:index + size] for index in range(0, len(items), size)]

def stable_request_id(job_id: str, inquiry_id: str, batch_no: int) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"{job_id}:{inquiry_id}:{batch_no}"))

def build_sync_payload(
    *, job_id, request_id, mode, account_handle,
    conversation, messages, batch_no, final_batch,
):
    return {
        "agentKey": "header-authenticated",
        "requestId": request_id,
        "accountHandle": account_handle,
        "syncMode": mode,
        "jobId": job_id,
        "batchNo": batch_no,
        "finalBatch": final_batch,
        "conversation": {
            "inquiryId": str(conversation["inquiry_id"]),
            "buyerExternalId": conversation.get("buyer_external_id"),
            "buyerName": conversation.get("buyer_name", ""),
            "country": conversation.get("country", ""),
            "subject": conversation.get("subject", ""),
            "sourceStatus": conversation.get("status", ""),
            "unreadCount": int(conversation.get("unread_count", 0)),
            "createdAtRaw": conversation.get("create_time", ""),
            "updatedAtRaw": conversation.get("last_time", ""),
        },
        "messages": [message.model_dump(mode="json", by_alias=True) for message in messages],
    }

class AlibabaSyncService:
    def __init__(self, bot, gateway, state_store, settings, sleeper=asyncio.sleep):
        self.bot = bot
        self.gateway = gateway
        self.state_store = state_store
        self.settings = settings
        self.sleeper = sleeper

    async def run_backfill(self) -> SyncSummary:
        job_id = self.state_store.get_or_create_active_job("backfill", self.settings.ACCOUNT_HANDLE)
        resume = self.state_store.resume_point(job_id)
        summary = SyncSummary(job_id=job_id, mode="backfill")
        for raw_conversation in await self.bot.get_all_conversations():
            inquiry_id = str(raw_conversation["inquiry_id"])
            if inquiry_id in resume.completed_inquiries:
                summary.skipped += 1
                continue
            self.state_store.mark_conversation_started(job_id, inquiry_id)
            try:
                messages = await self.bot.get_sync_history(inquiry_id=inquiry_id)
                batches = list(chunked(messages, self.settings.SYNC_BATCH_SIZE)) or [[]]
                for batch_no, batch in enumerate(batches, start=1):
                    request_id = stable_request_id(job_id, inquiry_id, batch_no)
                    payload = build_sync_payload(
                        job_id=job_id,
                        request_id=request_id,
                        mode="backfill",
                        account_handle=self.settings.ACCOUNT_HANDLE,
                        conversation=raw_conversation,
                        messages=batch,
                        batch_no=batch_no,
                        final_batch=batch_no == len(batches),
                    )
                    result = await self._push_with_retry(payload, request_id)
                    self.state_store.record_batch(job_id, inquiry_id, batch_no, request_id, result)
                self.state_store.mark_conversation_complete(job_id, inquiry_id)
                summary.completed += 1
            except CrmPermanentError as exc:
                self.state_store.mark_conversation_failed(job_id, inquiry_id, "permanent", str(exc))
                summary.failed += 1
        self.state_store.complete_job(job_id)
        return summary

    async def run_incremental_once(self) -> SyncSummary:
        job_id = self.state_store.start_job("incremental", self.settings.ACCOUNT_HANDLE)
        summary = SyncSummary(job_id=job_id, mode="incremental")
        for raw_conversation in await self.bot.get_changed_conversations(self.state_store.last_success_at()):
            inquiry_id = str(raw_conversation["inquiry_id"])
            messages = await self.bot.get_sync_history(inquiry_id=inquiry_id)
            request_id = stable_request_id(job_id, inquiry_id, 1)
            payload = build_sync_payload(
                job_id=job_id,
                request_id=request_id,
                mode="incremental",
                account_handle=self.settings.ACCOUNT_HANDLE,
                conversation=raw_conversation,
                messages=messages,
                batch_no=1,
                final_batch=True,
            )
            result = await self._push_with_retry(payload, request_id)
            self.state_store.record_batch(job_id, inquiry_id, 1, request_id, result)
            self.state_store.mark_conversation_complete(job_id, inquiry_id)
            summary.completed += 1
        self.state_store.complete_job(job_id)
        return summary

    async def run_forever(self) -> None:
        while True:
            await self.run_incremental_once()
            await self.sleeper(self.settings.SYNC_INTERVAL_SECONDS)

    async def _push_with_retry(self, payload: dict, request_id: str) -> dict:
        delays = (1, 2, 4)
        for attempt, delay in enumerate(delays, start=1):
            try:
                return self.gateway.sync_batch(payload, request_id)
            except CrmTransientError:
                if attempt == len(delays):
                    raise
                await self.sleeper(delay)
        raise AssertionError("retry loop exhausted without returning or raising")
```

Build batch payloads with `syncMode`, stable job/request IDs, account handle, normalized conversation snapshot, and serialized `SyncMessage` models. Never send system messages or attachments.

- [ ] **Step 5: Implement CLI modes**

`run_sync.py` supports:

```text
python -m alibaba_messenger.run_sync backfill
python -m alibaba_messenger.run_sync once
python -m alibaba_messenger.run_sync daemon
python -m alibaba_messenger.run_sync status
```

`backfill` resumes the active backfill job. `once` runs one incremental cycle. `daemon` starts the browser once and repeats every 300 seconds. `status` reads SQLite without starting Playwright and prints counts only.

- [ ] **Step 6: Run orchestration and CLI tests**

```powershell
python -m pytest tests/test_sync_service.py tests/test_runner_cli.py -v
```

Expected: PASS; no real browser, CRM, or Alibaba network call occurs in these tests.

- [ ] **Step 7: Review checkpoint**

Confirm SIGINT/KeyboardInterrupt closes browser and SQLite cleanly, daemon cannot overlap cycles, and logs contain counts/IDs rather than customer bodies. Do not commit.

---

### Task 11: End-to-end mock verification and operator documentation

**Files:**
- Create: `G:\FSH\alibb\tests\fixtures\alibaba_conversations.json`
- Create: `G:\FSH\alibb\tests\fixtures\alibaba_history_13907077489.json`
- Create: `G:\FSH\alibb\tests\test_sync_e2e.py`
- Modify: `G:\FSH\alibb\alibaba_messenger\README.md`
- Modify: `G:\FSH\CRM\fsh\docs\API_AGENT_HANDOFF.md`

- [ ] **Step 1: Create fictional redacted fixtures**

Fixtures contain at least two countries, two conversations, inbound/outbound text, duplicate text at distinct positions, a system event, a low-confidence timestamp, and more than 100 messages for one conversation. Use fictional names and no real inquiry IDs.

- [ ] **Step 2: Write the end-to-end mock test**

Run the Python sync service against a fake bot backed by fixtures and the isolated CRM endpoint. Assert CRM contains exact expected counts, one Lead per unmatched identity, correct final states, no system messages, no drafts, no tasks, and zero new records after a second full run.

- [ ] **Step 3: Run all alibb offline tests**

```powershell
python -m pytest tests -v
```

Expected: all tests PASS without accessing Alibaba or sending messages.

- [ ] **Step 4: Run the isolated CRM mock E2E test**

```powershell
$env:RUN_ALIBABA_SYNC_E2E='1'
$env:ESPOCRM_API_URL='http://localhost:18080/api/v1'
python -m pytest tests/test_sync_e2e.py -v
```

Expected: PASS and second-run created counts are zero.

- [ ] **Step 5: Document exact operator flow**

Update README and handoff docs with:

1. Copy `.env.example` to `.env` and inject secrets outside Git.
2. Register/rotate the Agent once and save the returned token securely.
3. Run `status`, then `backfill`.
4. Read the backfill summary and retry failed inquiry IDs.
5. Run the same backfill again to prove zero duplicates.
6. Start `daemon` for five-minute increments.
7. Recover from loginExpired/captcha/pageChanged without deleting SQLite.
8. State explicitly that attachments, official API data, outbound sending, and automated greetings are not part of this plan.

- [ ] **Step 6: Final verification**

CRM repository:

```powershell
$env:PYTHONUTF8='1'; python -m unittest tests.test_contracts tests.test_phase1 tests.test_alibaba_sync_contract -v
git diff --check
git status --short
```

Alibaba repository:

```powershell
python -m pytest tests -v
git diff --check
git status --short --ignored
```

Expected: tests PASS; only intended source, tests, docs, and examples are visible; secrets/Profile/logs/SQLite remain ignored.

- [ ] **Step 7: User review checkpoint**

Present both diffs and verification output to the user. Do not commit or push. Obtain explicit authorization before any future commit.

---

## Deferred plans

After this foundation is implemented and accepted, write separate plans in this order:

1. **Alibaba outbound execution plan:** enriched task payload, persistent `idempotencyKey`, post-send bubble verification, receipt IDs, terminal/transient error handling, daily automatic-greeting counters, and single-message live acceptance.
2. **Greeting automation plan:** 7/14/30-day progress rules, structured holiday calendar, CRM overrides, Campaign grouping, AI draft generation, batch preview/exclusion/approval, cooldown, and 30-per-day enforcement.

Neither deferred subsystem should be implemented as part of this plan.
