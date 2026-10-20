# Tasks: Deployment reconciliation

## Phase 1: Setup
- [x] T001 Record source/runtime comparison and network gates in `specs/012-deployment-reconcile/research.md` (FR-005/FR-006).
- [x] T002 Recheck production fingerprints/config and record preconditions in `docs/DEPLOYMENT_RECONCILE_2026-10-20.md` (FR-004).

## Phase 2: US1 Complete source and preserved fixes
- [x] T003 [US1] Add synthetic report-recovery/freshness/bounded-retry/concurrency regressions in `tests/wechat_accounts_contract.php` and `tests/morning_report_contract.php` and `tests/wechat_report_recovery_contract.php` (FR-003).
- [x] T004 [US1] Preserve and correct report recovery in `custom/Espo/Custom/Tools/Fusanhe/WeChatAccounts.php`, `WeChatApi.php` and `MorningReportService.php` (FR-001/FR-003).
- [x] T005 [US1] Preserve reviewed `custom/Espo/Custom/Tools/Fusanhe/acquisition-bridge.php` and `deploy/gateway-22005/deploy/supervisord.conf` (FR-001).
- [x] T006 [US1] Validate complete source, offline contracts and reproducible builds; record `specs/012-deployment-reconcile/verification.md` (FR-001/FR-005).

## Phase 3: US2 Data-preserving deployment
- [x] T007 [US2] Create verified database/data/source/env backups and record references in `docs/DEPLOYMENT_RECONCILE_2026-10-20.md` (FR-002/FR-004).
- [x] T008 [US2] Restore isolated copy, rebuild missing schema and validate counts/auth/evidence APIs in `specs/012-deployment-reconcile/verification.md` (FR-004).
- [x] T009 [US2] Deploy reviewed release with recovery boundaries and validate source/counts/health in `docs/DEPLOYMENT_RECONCILE_2026-10-20.md` (FR-001/FR-002/FR-005).

## Phase 4: US3 Direct company broadband
- [ ] T010 [US3] Verify domain, WAN, router, inbound and provider prerequisites in `docs/DEPLOYMENT_RECONCILE_2026-10-20.md` (FR-006).
- [ ] T011 [US3] Configure verified private-origin HTTPS/router/DNS entry in `deploy/company-broadband/` after T010 passes (FR-006/FR-007).
- [ ] T012 [US3] Validate external TLS/login/WebSocket and record result or exact pending prerequisite in `specs/012-deployment-reconcile/verification.md` (FR-006/FR-007).

## Phase 5: Closeout
- [x] T013 Record source/tests/recovery/remaining gates in `docs/DEPLOYMENT_RECONCILE_2026-10-20.md` and run feature convergence (FR-005).

## Dependencies and delivery
T003 precedes T004; T004/T005 precede T006; T002/T006/T007 precede T008; T008 precedes T009. T010 is independent of code repair; T011/T012 depend on it. US1 is the independently testable repair increment. No parallel source mutations are required. External prerequisites remain unchecked.

## Phase 6: Convergence

- [ ] T014 [US3] Complete the direct company-broadband cutover in `deploy/company-broadband/` and record external validation in `docs/DEPLOYMENT_RECONCILE_2026-10-20.md` after router administrator access, public WAN and provider conditions are verified; closes the remaining FR-006 / US3 operational gap (partial, HIGH).
