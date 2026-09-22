# Alibaba Outbound Worker & Heartbeat Integration Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish an active outbound dispatch loop and heartbeat health reporter in `G:\FSH\alibb` connected to CRM's claim/sending/result endpoints, allowing automated message delivery with human-cooldown simulation, double deduplication, and safe pause gating.

**Architecture:** A dedicated `OutboundWorker` pulls approved tasks from CRM (`POST /Fusanhe/agent/claim`), safely handles `paused: true` (FUSANHE_OUTBOUND_PAUSED), marks tasks sending (`POST /Fusanhe/agent/task/:id/sending`), simulates or executes delivery through `AlibabaMessengerBot.send_message`, and writes receipts back to CRM (`POST /Fusanhe/agent/task/:id/result`). Concurrently, a background heartbeat loop reports agent health (`POST /Fusanhe/agent/heartbeat`) every 60s, reporting online/offline state based on browser login status. CRM's `taskPayload` is enriched to include `inquiryId` and `buyerName`.

**Tech Stack:** Python 3.10+, Playwright, asyncio, requests, pytest; EspoCRM (PHP 8.2), MariaDB.

**Spec Reference:** `docs/superpowers/specs/2026-09-21-alibaba-messenger-crm-integration-design.md` (Sections 4.4, 4.5, 9.1)

---

## Global Constraints

- Never commit secrets, tokens, cookies, or browser profiles to Git.
- Maintain idempotent message execution: do not report success without receipt or bubble verification.
- Always respect CRM `paused: true` by cooling down and logging without throwing errors.
- Never crash the heartbeat loop when CRM is temporarily unreachable (apply exponential backoff).
- All CRM requests must carry `X-Request-Id` and agent authorization headers.

---

## File Structure & Map

### CRM Component (`G:\FSH\CRM\fsh`)
- Modify: `custom/Espo/Custom/Tools/Fusanhe/WorkflowService.php`
  - In `taskPayload(Entity $task)`: enrich payload with `inquiryId`, `buyerName`, `channelType`, `triggerType`.
- Test: `tests/test_alibaba_outbound_contract.py`
  - Verify `taskPayload` structure and required fields.

### alibb Component (`G:\FSH\alibb`)
- Modify: `alibaba_messenger/crm_gateway.py`
  - Implement `heartbeat(status, last_error)`
  - Implement `claim()`
  - Implement `mark_sending(task_id)`
  - Implement `report_result(task_id, success, platform_message_id, error_message)`
- Create: `alibaba_messenger/outbound_worker.py`
  - `OutboundWorker`: manages claim-sending-result lifecycle and heartbeat task.
  - Supports dry-run and mock mode without browser interaction.
- Create: `alibaba_messenger/run_worker.py`
  - CLI runner supporting `--headless`, `--dry-run`, `--once`, `--interval`.
- Tests:
  - Modify: `tests/test_crm_gateway.py`
    - Add tests for heartbeat, claim, mark_sending, report_result.
  - Create: `tests/test_outbound_worker.py`
    - Test claim with paused=True.
    - Test claim, mark_sending, bot execution, and report_result.
    - Test send failure and error reporting.
    - Test heartbeat cycle.

---

## Tasks

### Task 1: Enrich CRM OutboundTask Payload with Alibaba Context

**Files:**
- Modify: `G:\FSH\CRM\fsh\custom\Espo\Custom\Tools\Fusanhe\WorkflowService.php:799-812`
- Create: `G:\FSH\CRM\fsh\tests\test_alibaba_outbound_contract.py`

**Interfaces:**
- Consumes: `OutboundTask`, `AIReplyDraft`, `ExternalConversation`
- Produces: `taskPayload` containing:
  ```json
  {
    "id": "task-uuid",
    "idempotencyKey": "key",
    "conversationId": "conv-uuid",
    "inquiryId": "13907077489",
    "buyerName": "Buyer Name",
    "channelId": "channel-uuid",
    "channelType": "Alibaba",
    "executionMode": "mock|real",
    "body": "Reply body",
    "triggerType": "manual",
    "claimExpiresAt": "2026-09-22 10:05:00"
  }
  ```

- [ ] **Step 1: Write offline unit test for CRM task payload**

```python
# G:\FSH\CRM\fsh\tests\test_alibaba_outbound_contract.py
import re
from pathlib import Path

def test_task_payload_includes_inquiry_and_buyer():
    service_file = Path(__file__).resolve().parent.parent / "custom/Espo/Custom/Tools/Fusanhe/WorkflowService.php"
    content = service_file.read_text(encoding="utf-8")
    assert "function taskPayload" in content
    assert "'inquiryId'" in content
    assert "'buyerName'" in content
    assert "'channelType'" in content
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_alibaba_outbound_contract.py`
Expected: FAIL (inquiryId not found in WorkflowService.php)

- [ ] **Step 3: Update `WorkflowService::taskPayload`**

Edit `G:\FSH\CRM\fsh\custom\Espo\Custom\Tools\Fusanhe/WorkflowService.php`:
```php
    private function taskPayload(Entity $task): array
    {
        $draft = $this->requireEntity('AIReplyDraft', (string) $task->get('replyDraftId'));
        $body = $this->taskBody($task, $draft);
        $convId = (string) $task->get('conversationId');
        $conversation = $convId !== '' ? $this->em->getEntityById('ExternalConversation', $convId) : null;
        $channelId = (string) $task->get('channelId');
        $channel = $channelId !== '' ? $this->em->getEntityById('ExternalChannel', $channelId) : null;

        return [
            'id' => $task->getId(),
            'idempotencyKey' => $task->get('idempotencyKey'),
            'conversationId' => $convId,
            'inquiryId' => $conversation ? (string) ($conversation->get('externalId') ?: '') : '',
            'buyerName' => $conversation ? (string) ($conversation->get('name') ?: '') : '',
            'channelId' => $channelId,
            'channelType' => $channel ? (string) ($channel->get('type') ?: 'Alibaba') : 'Alibaba',
            'executionMode' => $task->get('executionMode') ?: 'mock',
            'body' => $body,
            'triggerType' => (string) ($draft->get('triggerType') ?: 'manual'),
            'claimExpiresAt' => $task->get('claimExpiresAt'),
        ];
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_alibaba_outbound_contract.py`
Expected: PASS

---

### Task 2: Extend alibb CrmGateway with Outbound & Heartbeat Methods

**Files:**
- Modify: `G:\FSH\alibb\alibaba_messenger\crm_gateway.py`
- Modify: `G:\FSH\alibb\tests\test_crm_gateway.py`

**Interfaces:**
- Produces:
  - `gateway.heartbeat(status="online", last_error=None) -> dict`
  - `gateway.claim() -> dict`
  - `gateway.mark_sending(task_id: str) -> dict`
  - `gateway.report_result(task_id: str, success: bool, platform_message_id=None, error_message=None) -> dict`

- [ ] **Step 1: Write tests for the new gateway methods**

In `G:\FSH\alibb\tests\test_crm_gateway.py`, add:
- `test_heartbeat_success`
- `test_claim_returns_paused_or_task`
- `test_mark_sending_success`
- `test_report_result_success_and_failure`

- [ ] **Step 2: Run test to verify failure**

Run: `pytest tests/test_crm_gateway.py`
Expected: FAIL (missing methods)

- [ ] **Step 3: Implement methods in `CrmGateway`**

In `G:\FSH\alibb\alibaba_messenger\crm_gateway.py`:
- Add `_headers(self, request_id: str | None = None) -> dict`: sends `X-Agent-Key`, `X-Agent-Token`, and `X-Automation-Token`.
- Add `heartbeat(...)`
- Add `claim(...)`
- Add `mark_sending(...)`
- Add `report_result(...)`

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_crm_gateway.py`
Expected: PASS

---

### Task 3: Build OutboundWorker Core Engine

**Files:**
- Create: `G:\FSH\alibb\alibaba_messenger\outbound_worker.py`
- Create: `G:\FSH\alibb\tests\test_outbound_worker.py`

**Interfaces:**
- `OutboundWorker(bot, gateway, settings)`
  - `async send_heartbeat() -> bool`
  - `async process_one_task(task: dict) -> bool`
  - `async poll_and_execute_once() -> bool`
  - `async run_loop(stop_event: asyncio.Event | None = None)`

- [ ] **Step 1: Write tests for OutboundWorker**

Cover:
1. `test_worker_heartbeat_online_when_logged_in`
2. `test_worker_heartbeat_offline_when_not_logged_in`
3. `test_worker_claim_paused_logs_and_returns_false`
4. `test_worker_process_mock_task_succeeds`
5. `test_worker_process_real_task_calls_bot_and_reports`
6. `test_worker_process_task_failure_reports_error`

- [ ] **Step 2: Run test to verify failure**

Run: `pytest tests/test_outbound_worker.py`
Expected: FAIL (file does not exist)

- [ ] **Step 3: Implement `OutboundWorker`**

Key logic in `outbound_worker.py`:
- Extracts `task_id`, `inquiry_id`, `buyer_name`, `body`, `execution_mode`.
- If `execution_mode == "mock"`: avoids browser, reports simulated receipt ID.
- If `execution_mode == "real"`: calls `bot.send_message(buyer_name=buyer_name or inquiry_id, message=body, inquiry_id=inquiry_id)`.
- Handles `NEED_LOGIN`, `DUPLICATE_IGNORED`, `SEND_FAILED`, and `SENT`.
- Manages heartbeat interval (60s) and task polling interval (default 15s).

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_outbound_worker.py`
Expected: PASS

---

### Task 4: CLI Runner `run_worker.py` & End-to-End Verification

**Files:**
- Create: `G:\FSH\alibb\alibaba_messenger\run_worker.py`
- Modify: `G:\FSH\alibb\alibaba_messenger\README.md`

- [ ] **Step 1: Implement CLI in `run_worker.py`**
- Arguments:
  - `--headless`
  - `--dry-run` (simulate bot execution)
  - `--once` (single poll tick, exit 0)
  - `--interval` (seconds between task claims)
  - `--allow-remote`
- Handles SIGINT/SIGTERM gracefully, closes browser and logs summary.

- [ ] **Step 2: Write verification test for `run_worker.py`**
- In `tests/test_outbound_worker.py`, add CLI invocation test with `--once` and `--dry-run`.

- [ ] **Step 3: Update README.md with Worker usage and safety instructions**
- Document how to start the Outbound Worker.
- Note the relation with `FUSANHE_OUTBOUND_PAUSED=true`.
