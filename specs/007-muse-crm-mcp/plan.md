# Implementation Plan: Muse Code CRM MCP Gateway

1. Add provenance and contact-policy fields to Lead metadata and retain the
   existing identity/conversation/message model.
2. Implement `MuseCrmService` with capability checks, strict validation,
   source-identity upsert, conflict-safe activity recording and safe response
   projections.
3. Add authenticated GET/POST actions and routes under `/Fusanhe/muse/*`.
4. Add offline contracts, API examples and Muse Code MCP tool mapping.
5. Run PHP lint, contract tests, compose validation and the existing offline
   regression suite. Use an isolated EspoCRM runtime for behavior checks when
   the test stack is available.

The service writes through `ServiceKernel` so existing hooks, audit records and
the global outbound pause remain authoritative. It never calls a channel
connector or creates an approved OutboundTask.
