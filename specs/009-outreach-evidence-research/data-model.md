# Data Model: CRM 触达证据与 AI 背调

## OutreachEvidence

| Field | Meaning |
|---|---|
| `idempotencyKey` | Future Muse or CRM caller's stable attempt key; unique |
| `requestHash` | Canonical request hash used for replay conflict detection |
| `channelType` / `channelAccountId` | Platform and sending account |
| `profileUrl` / `externalMessageId` | Public profile and platform message reference |
| `messageBody` / `sendStatus` / `sentAt` | What was sent and the observed result |
| `customerSnapshot` | Bounded public customer fields captured at send time |
| `screenshotFileKey` and image metadata | Private screenshot bytes and integrity metadata |
| `researchStatus` / `researchData` | Current AI research state and structured report |
| `leadId`, `accountId`, `contactId`, `conversationId`, `messageId` | Optional CRM links; the target customer is required in v1 |

## ProspectResearch

One research snapshot for an `OutreachEvidence` record. Stores the sanitized input, human-readable report, structured data, verified source URLs, search queries, model, prompt version, timestamps and a bounded error code.

## Storage and access

Screenshot bytes live in the existing private `MediaStorage`; the database stores only a random file key and integrity metadata. API reads are ACL-scoped and return a data URL only after entity-level permission checks. No public URL is generated.
