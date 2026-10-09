# Feature Specification: Muse Code CRM MCP Gateway

**Feature Branch**: `codex/muse-crm-mcp`
**Created**: 2026-10-01
**Status**: Draft
**Input**: Add a CRM-side integration contract for Muse Code CLI + CRM MCP.

## Scope

This feature exposes a narrow, agent-authenticated CRM gateway that an MCP
server can wrap for Muse Code. It stores prospect records, source provenance,
campaign metadata, outreach content and delivery outcomes in the existing CRM
Lead, ExternalIdentity, ExternalConversation and ExternalMessage entities.

The gateway does not send messages, browse platforms, accept credentials from
Muse prompts, or expose generic EspoCRM CRUD. Outbound delivery remains a
separate approved task/connector concern.

## Requirements

### MUSE-CRM-01 Prospect lookup

An authenticated Muse agent can search prospects by its stable source ID,
email, phone or name. Results contain only CRM identifiers, provenance,
contact policy and fields needed to decide whether to update or create a
prospect. Results never include credentials, raw audit payloads or unrelated
customer records.

### MUSE-CRM-02 Idempotent prospect upsert

An authenticated Muse agent can create or update a prospect using a stable
`sourceSystem + sourceId` identity. Repeating the same request returns the
same Lead and ExternalIdentity without duplicate records. A confirmed existing
Account, Contact or Lead is returned as a match and is never silently merged or
overwritten.

### MUSE-CRM-03 Provenance and contact policy

Every Muse prospect stores source system, source ID, optional public source URL,
campaign key and contact policy (`unknown`, `allowed`, `optedOut`, `restricted`).
An opted-out or restricted prospect is marked do-not-contact and the activity
gateway must reject new outbound records for it.

### MUSE-CRM-04 Activity and content recording

An authenticated Muse agent can create or update an external conversation and
record an inbound or outbound message with an external message ID, body,
channel, timestamp, campaign and delivery status. Repeating an external
message ID for the same conversation is idempotent; a conflicting body returns
conflict. Recording a message never authorizes or triggers external delivery.

### MUSE-CRM-05 Agent authentication and capability

All gateway routes require the existing per-agent credential headers
`X-Agent-Key` and `X-Agent-Token`, and the registered agent must include the
`MuseCRM` capability. Bootstrap registration remains the only operation using
the shared automation token.

### MUSE-CRM-06 Audit and correlation

Successful and rejected writes record an audit event with agent identity,
request ID, operation type and safe identifiers. API responses return the
request ID; exception details and secrets are never returned.

### MUSE-CRM-07 Bounded payloads

The gateway validates field lengths, supported channels/statuses, timestamps,
and payload size. It does not persist an entire Muse run transcript or prompt
unless it is explicitly supplied as the message body/activity content.

## Non-goals

- Implementing the MCP JSON-RPC server itself; the stable CRM HTTP contract is
  the first boundary, and a thin MCP wrapper can expose these tools later.
- Automatic bulk sending, platform browser automation, reply generation, or
  campaign scheduling.
- Generic Lead/Message CRUD for an Agent.
