# Data and state compatibility

Existing CRM records, files and data volumes remain authoritative. Install existing main OutreachEvidence and ProspectResearch definitions/relationships through Espo rebuild without reimporting customers.

Report states remain preparing/sent/failed/uncertain/skipped. Known rejected deliveries may recover at most twice with a later inbound context differing from the prior attempt. Sent, uncertain, preparing and token-expired results never become automatic resend candidates. Preserve attempt history; sanitize internal client/context hashes in report projections.

Shared WeChat context/cursor uses the observed pre-poll snapshot as a compare-and-swap condition. If another poll wins, merge inbox records while retaining the winning context/cursor. Exceptions after submission are uncertain.

Release metadata: source commit, expected file fingerprints, overrides, backup manifest, health/count checks and recovery path. Customer data, account secrets, browser profiles and backups remain outside Git.
