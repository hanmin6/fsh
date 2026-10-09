# Tasks: CRM 触达证据与 AI 背调

**Input**: Design documents from `/specs/009-outreach-evidence-research/`

## Phase 1: Setup

- [x] T001 Create feature specification and implementation plan in `specs/009-outreach-evidence-research/`
- [x] T002 Add entity metadata and rebuild validation
- [x] T003 [P] Add contract test fixtures for bounded screenshot and research payloads

## Phase 2: Foundational

- [x] T004 Implement screenshot validation and private storage policy in `custom/Espo/Custom/Tools/Fusanhe/OutreachEvidencePolicy.php`
- [x] T005 [P] Add `OutreachEvidence` and `ProspectResearch` metadata
- [x] T006 Add routes and ACL-scoped API action shells

## Phase 3: User Story 1 - 留存每次触达证据 (P1)

- [x] T010 [P] Contract tests for evidence idempotency, screenshot bounds and no-send boundary in `tests/test_outreach_evidence_contract.py`
- [x] T011 Implement `OutreachEvidenceService::record` with idempotency, customer links, screenshot storage and audit
- [x] T012 Implement create/read/screenshot API actions and route contracts
- [x] T013 Expose bounded evidence projections without raw secrets or public file URLs

## Phase 4: User Story 2 - AI 背调客户 (P2)

- [x] T020 [P] Add injected-gateway tests for source filtering, failure state and retryability
- [x] T021 Implement `OutreachEvidenceService::research` using structured public-profile input and `TextGateway::research`
- [x] T022 Add research API action and persistence of report/model/prompt version/source URLs
- [x] T023 Add a CRM job/command entry point for retrying pending research without sending

## Phase 5: User Story 3 - 在客户工作台查看证据 (P3)

- [ ] T030 [P] Add UI/domain tests for evidence and research states
- [x] T031 Add evidence summary to customer/conversation workbench
- [x] T032 Add private screenshot preview and source links with ACL-aware empty/error states

## Phase 6: Verification

- [x] T040 [P] Update `docs/PROJECT_STATUS.md` and `docs/API_AGENT_HANDOFF.md`
- [x] T041 Run PHP lint, metadata validation, contract tests and `make verify-offline`
- [x] T042 Confirm global outbound pause and no Muse/external connector calls in verification
