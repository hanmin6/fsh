# Muse CRM MCP Gateway verification

Date: 2026-10-01.

## Offline checks

- `tests.test_muse_crm_contract` covers Lead provenance fields, route auth,
  capability gating, no-send boundary and MCP documentation.
- Existing API and Agent credential contracts remain green.
- JSON metadata and routes pass parser validation; `git diff --check` is clean.
- `python3 -m unittest tests.test_muse_crm_contract tests.test_api_contract
  tests.test_agent_credentials tests.test_phase1 -v`: 39 tests passed.
- `make verify-offline`: Compose configuration and the 49-test Python suite
  passed. The PHP contract phase could not start because the local Docker
  daemon socket was unavailable; no PHP binary is installed locally.

## Runtime checks

Pending isolated EspoCRM runtime execution. The runtime fixture must register a
`MuseCRM` Agent, then verify:

1. first prospect upsert creates one Lead and one ExternalIdentity;
2. the same source ID upsert is deduplicated;
3. queued activity creates one conversation and one message without an
   OutboundTask or connector call;
4. repeating the same message ID is idempotent and changing its body returns
   conflict;
5. opted-out prospects reject outbound activity;
6. missing/wrong capability or credential returns a generic forbidden response;
7. inbound and delivered outbound activities update conversation state and
   Lead provenance/last-contact fields.

No real Muse account, customer data, or external channel is used by these
checks. Runtime and PHP lint remain pending until an EspoCRM/PHP environment
is available.
