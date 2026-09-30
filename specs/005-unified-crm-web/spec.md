# Unified CRM Web 1.0.0

Approved design: design.md. One five-page frontend based on crm-web-v0.5.0.

## User stories
US1: See Alibaba/MIC capture health, last success, compact healthy states and expanded actionable errors, independently. Unknown is not success.
US2: Handle identities, takeover, drafts/review, handoff and send queues without leaving the workspace; preserve message pagination and server policy.
US3: Browse customers, record audited S/A/B/C ratings, inspect both-channel history/evidence and convert suggestions to tasks.
US4: Browse product specifications, certificates, knowledge and materials; edit via controlled existing record forms where appropriate. Creative flows expose their actual provider availability and never pass simulation off as media.
US5: Publish one versioned main baseline, preserve historical UI refs as tags and archive obsolete UI branches after verifying their heads.

## Acceptance
Capture success and failure/recovery are independently testable; failed recheck retains error until success. Real writes use existing ACL/workflow gates; unknown stop state never claims safe sending. Demo operates only on synthetic local fixtures. Desktop/mobile, deep-links, back, keyboard and errors verified. Builds and relevant regression checks pass; unavailable deployment/provider checks are recorded.
