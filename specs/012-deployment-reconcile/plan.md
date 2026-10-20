# Implementation Plan: Deployment reconciliation

**Branch**: `codex/crm-deployment-sync-20261020` | **Date**: 2026-10-20 | **Spec**: [spec.md](spec.md)

## Summary
Use main 8918944 as the complete source baseline. Preserve production report fixes, correct recovery edge cases, archive the acquisition bridge/recovery supervisor configuration, and deploy a fingerprinted release after backup and isolated checks. Assess company broadband independently; switch fshcrm.xyz only after router/provider and inbound reachability pass.

## Technical Context
PHP 8.3 / EspoCRM 10.0.8 Apache, MariaDB 11.4, React 19/TypeScript/Vite, Python channel clients, Ubuntu Docker host; three human users. Preserve the persistent data volumes, server.env, native Espo login, feature flags and global outbound pause. Changing the current symlink alone does not update existing container mounts; recreate application containers without recreating the database.

Verification: frontend unit/native tests and both existing builds; Python offline contracts; PHP report/WeChat/evidence/research regressions and lint; isolated restored database, metadata rebuild, existing table counts and HTTP authorization; final app-check and source/HTTP fingerprints. No new interface design or provider/customer sends.

## Constitution Check
Specification precedes repair; outbound control remains paused; tests use synthetic data and fake transports; secrets stay outside Git; schema changes have verified backup/restore; unfinished network gates remain explicit. All design gates pass.

## Files and owners
- custom/Espo/Custom/Tools/Fusanhe/{MorningReportService,WeChatAccounts,WeChatApi}.php: preserve fixes; late rejection recovery only; shared context compare-and-swap; any post-submission exception is uncertain.
- custom/Espo/Custom/Tools/Fusanhe/acquisition-bridge.php: preserve after entrypoint/secret review.
- deploy/gateway-22005/deploy/supervisord.conf: retain recovery agent configuration.
- tests/{morning_report_contract,wechat_accounts_contract,wechat_report_recovery_contract}.php: report retry and concurrency regressions.
- docs/DEPLOYMENT_RECONCILE_2026-10-20.md: release, rollback and direct-network status.
- deploy/company-broadband/: private-origin HTTPS entry if prerequisites pass.

## Deployment and rollback
1. Reinspect fingerprints/config/schema and abort on unreviewed drift.
2. Back up database, Espo data, mounted source, env and gateway supervisor into a restricted directory with SHA-256 manifest.
3. Stage complete source plus overrides; validate a restored copy in task-specific isolated volumes.
4. Enter maintenance, pause CRM background services, take final consistent pre-migration backups, switch release, recreate application containers against existing env/volumes/images, rebuild metadata, and verify counts/auth/health.
5. On failure stop updated workers, restore prior pointer/source and required pre-migration data, recreate prior application and verify before releasing maintenance.
6. Keep DNS unchanged until company broadband's WAN, forwarding, permitted ports, TLS/login/WebSocket and applicable provider conditions are verified. Do not substitute another cloud ingress.

## Design scope
Existing evidence/research APIs and entities are restored from specs/009, not redesigned. The independent channel gateway already runs main-equivalent executable files and must retain state/config. Network prerequisites are operational gates, separate from code repair.
