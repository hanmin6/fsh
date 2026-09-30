# Plan
Base bd4a2c8; preserve main sync/client changes, selectively port HIG workflow/permission/layout fixes. React19/TypeScript/Vite/lucide, existing brand CSS and single workspace mount. Feature modules: capture, workflow, queues, insights, records. Existing Espo AJAX and server ACL remain authoritative. Capture observations are derived only from reported state/successful source sync, with provenance and unknown states. Extend source-aware history filtering. Audited rating metadata/hook. Single package 1.0.0 and crm-web-v1.0.0 tag; archive old UI heads before remote cleanup.

Verification: npm tests/build; frontend node tests; Python contracts; PHP lint; browser synthetic fixtures desktop/mobile and workflow interactions. Isolated Docker runtime where available. Rollback main to tagged baseline through a revert, restore archived branches from tags; never alter production data/credentials or enable sends.

Constitution check: spec before code; server state authority; no private fixtures; outbound policy unchanged; record evidence and limitations.
