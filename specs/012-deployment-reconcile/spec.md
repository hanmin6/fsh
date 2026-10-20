# Feature Specification: Reconcile the Guangzhou deployment and connect company broadband

**Feature Branch**: `codex/crm-deployment-sync-20261020`
**Created**: 2026-10-20
**Status**: In progress
**Input**: 补齐广州主机与 GitHub 的差异，保留线上修正，并用公司宽带直接接入用户确认的 CRM 域名。

## User Scenarios & Testing

### User Story 1 - A complete, reproducible CRM release (Priority: P1)

The operator can maintain the current CRM from one complete release without losing the fixes already used by colleagues.

**Independent Test**: Compare the deployed release with its recorded source, rebuild the existing pages, and exercise the restored evidence/backstory feature in an isolated copy.

**Acceptance Scenarios**:
1. Given the mixed deployment, when it is reconciled, then the existing pages and screenshot reply feature remain available and their complete source is included.
2. Given registered evidence/backstory actions with missing implementations, when reconciliation is deployed, then those actions resolve to installed implementations and their existing authorization rules remain enforced.
3. Given the production morning-report retry fixes, when code is reconciled, then rejected deliveries recover only with fresh context and bounded attempts; ambiguous submissions are never automatically resent.

### User Story 2 - Preserve business data and recoverability (Priority: P1)

The operator can recover the prior deployment if verification fails while retaining existing business records, credentials, attachments, and unrelated services.

**Independent Test**: Validate backup checksums and restore the changed schema/data in an isolated copy before production changes.

**Acceptance Scenarios**:
1. Given a deployment update, when it starts, then verified backups and a rollback procedure exist first.
2. Given existing customer records and outbound controls, when deployment finishes, then records remain available, native login remains required, and global outbound pause stays enabled.
3. Given the independent channel gateway, when CRM source is reconciled, then the gateway's recovery configuration remains present and its running business code is not overwritten with old copies.

### User Story 3 - Use the company broadband entry (Priority: P2)

The three colleagues can open the confirmed CRM domain through company broadband using encrypted access and their existing accounts.

**Independent Test**: Access the confirmed domain from an external network, verify its certificate and login protection, then confirm the request reaches the Guangzhou application directly.

**Acceptance Scenarios**:
1. Given verified public reachability and authorized router access, when the direct entry is enabled, then external encrypted requests and live updates reach the CRM.
2. Given missing router access, public addresses, permitted inbound ports, or required provider/compliance conditions, when checks run, then the exact unmet condition is reported and the domain is not switched to an unverified destination.

### Edge Cases

- Source changes after inspection: fail the deployment precondition and re-evaluate before overwriting.
- Failure during metadata update: keep maintenance boundaries and use the verified recovery procedure.
- Rejection without a new inbound context, exhausted retries, uncertain response, or noon cutoff: do not resend.
- Dynamic public address, upstream NAT, or missing public IPv6: require a verified reachable entry and address-update policy.
- The latest message spells `fshcrm.xy`; the previously purchased domain is `fshcrm.xyz`. Domain confirmation gates domain changes only.

## Requirements

### Functional Requirements

- **FR-001**: Preserve production-only fixes and include complete source for the deployed pages and missing evidence/backstory behavior.
- **FR-002**: Keep existing authentication, permissions, business data, attachment storage, and paused outbound state.
- **FR-003**: Preserve bounded report-rejection recovery with fresh context, ambiguity protection, and concurrency checks.
- **FR-004**: Create verified backups and a documented rollback before deployment; validate schema changes in isolation.
- **FR-005**: Record a traceable source version, deployment manifest, relevant test evidence, and remaining external dependencies.
- **FR-006**: Enable direct company-broadband access only after domain identity, public reachability, router forwarding, encryption, and applicable provider requirements are established.
- **FR-007**: Expose only the web entry required for CRM; keep databases, file sharing, administration, and unrelated applications outside that entry.

### Key Entities

- Release record: source version, file fingerprints, backup reference, validation, recovery instructions.
- Report delivery: existing outcome, context freshness, attempt history, and final delivery state.
- Direct-entry assessment: confirmed domain, address, router access, reachability, and outstanding conditions.

## Success Criteria

### Measurable Outcomes

- **SC-001**: All reconciled release files match their recorded source or documented production overrides.
- **SC-002**: The current pages rebuild successfully, missing evidence/backstory actions pass isolated authorization checks, and report-recovery regressions pass.
- **SC-003**: The update preserves existing business-record counts and the four core CRM services return healthy.
- **SC-004**: Direct domain access passes external certificate, anonymous-access rejection, and live-update checks, or each unmet external prerequisite is explicitly recorded without claiming connection success.

## Assumptions

- This repairs and preserves existing product behavior; it does not authorize customer messages, new AI providers, paid infrastructure, or changing the corporate website.
- The existing shared-folder machine remains the business host.
- Domain confirmation and router/ISP facts are deployment gates; code repair can proceed independently.
