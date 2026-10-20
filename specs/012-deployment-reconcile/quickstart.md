# Validation guide

1. Run `SPECIFY_FEATURE_DIRECTORY=specs/012-deployment-reconcile make spec-check` and `git diff --check`.
2. Run frontend `npm ci`, `npm test`, `npm run build`, sales Vite build and native frontend contracts.
3. Execute report/WeChat/evidence/research PHP contracts and lint against staged source in an isolated container, without provider credentials.
4. Restore backup into task-specific volumes; rebuild metadata, compare existing table counts, and test evidence API authentication/ACL.
5. Deploy after preconditions/backup gates. Recheck core health, record counts, native login, outbound pause and served file fingerprints.
6. Verify router WAN/public address, permitted inbound 443 and provider requirements before DNS. Validate direct TLS/login/live updates from an outside network.
