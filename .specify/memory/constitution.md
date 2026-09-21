# 福三和 CRM Constitution

## Core Principles

### I. Specification Before Change
Every behavior-changing feature, integration, migration, or cross-component refactor MUST have a
feature directory under `specs/` before implementation begins. Its `spec.md` MUST describe user
value and testable outcomes; its `plan.md` MUST describe affected architecture and compatibility
boundaries; and its `tasks.md` MUST trace executable work to requirements. Existing production
behavior is evidence, not an excuse to omit a specification. Emergency repairs MAY use a shortened
bug workflow, but MUST record the defect, expected behavior, verification, and rollback path.

### II. Human-Controlled and Secure by Default
Outbound customer communication MUST remain human-approved unless a later specification explicitly
defines, reviews, and enables an automation policy. Global stop controls MUST fail closed. Secrets,
credentials, tokens, customer data, and raw private materials MUST NOT enter Git, specifications,
logs, screenshots, fixtures, or AI prompts. Authentication and authorization MUST be enforced at
the server boundary; client visibility and feature flags MUST NOT be treated as access control.

### III. Contract and State Integrity
Public APIs, entity schemas, uniqueness rules, and business state transitions MUST be explicit,
versioned when externally consumed, and protected by contract tests. Mutating operations that can
be retried MUST be idempotent. Server-side state machines are authoritative; Web and Android
clients MUST not invent transitions or bypass permissions. Cross-component changes MUST name the
contract owner and include compatibility or migration handling.

### IV. Evidence Before Completion
No task, requirement, or release may be marked complete solely from code inspection or a successful
build. Verification MUST be proportionate to risk and MUST include the repository's relevant
contract, regression, runtime, security, and client build checks. New behavior MUST add or update
tests that fail without the intended behavior. Any skipped check, warning, external dependency, or
unavailable environment MUST be reported as an unresolved limitation rather than silently treated
as success.

### V. Auditable, Reversible Operations
Customer-impacting actions, identity linkage, approvals, sending, credential lifecycle changes, and
administrative state transitions MUST produce auditable records without exposing secrets. Database
migrations, deployment changes, and operational automation MUST include a rollback or recovery
procedure. Destructive operations MUST identify their exact scope and require explicit operator
intent. Production-facing integrations MUST expose actionable health, retry, and failure evidence.

## Product and Technology Boundaries

- EspoCRM and MariaDB remain the system of record for CRM, conversation, workflow, and audit data.
- `custom/Espo/Custom/` owns server metadata, services, routes, and business state enforcement;
  `client/custom/src/` owns the Web experience; `android-client/` owns the mobile client.
- Shared business concepts MUST use consistent names and identifiers across PHP, JavaScript,
  Kotlin, tests, and specifications.
- Real channel integration priority is official API, supported email/interface combination,
  browser automation, then Windows UI automation. Any lower-priority mechanism MUST document why
  safer supported mechanisms are unavailable.
- The Android client MUST use a scoped user authentication design and MUST NOT store or reuse an
  administrator password.
- Feature flags control rollout and visibility only; authorization rules remain mandatory.
- Repository-managed configuration MAY contain safe defaults, but environment-specific secrets and
  mutable runtime data MUST remain outside version control.

## Spec-Driven Delivery Workflow

1. Establish or amend this constitution only when governance changes.
2. Run the Spec Kit specification workflow for each bounded change: specify, clarify when needed,
   plan, checklist, tasks, analyze, implement, and converge.
3. Specifications MUST separate confirmed current behavior, intended new behavior, assumptions,
   and known gaps. A baseline specification MUST NOT falsely mark roadmap work as implemented.
4. Planning MUST cite real repository paths, existing dependencies, contract owners, test commands,
   data migration needs, security impact, and rollback strategy.
5. Tasks MUST be small, dependency-ordered, independently verifiable where practical, and mapped to
   a requirement or user story. Checkbox state is a claim; test output and runtime evidence are the
   proof.
6. Analysis MUST report constitution violations, uncovered requirements, terminology drift, and
   untestable success criteria before implementation.
7. Convergence MUST compare the present codebase with the active feature artifacts. Remaining gaps
   stay open as tasks; the feature is complete only when convergence is clean or exceptions are
   explicitly approved and documented.

## Governance

This constitution governs all repository work and overrides conflicting informal practices. An
amendment MUST explain its impact, update this file, and use semantic versioning: MAJOR for removed
or incompatible principles, MINOR for new principles or materially expanded obligations, and PATCH
for non-semantic clarification. Every feature plan and review MUST include a constitution check.
Exceptions require a written rationale, named owner, risk, expiry or removal condition, and review
approval in the relevant feature artifacts. The project `README.md`, `docs/PROJECT_STATUS.md`, and
active feature artifacts provide operational guidance but cannot weaken a constitutional MUST.

**Version**: 1.0.0 | **Ratified**: 2026-09-21 | **Last Amended**: 2026-09-21
