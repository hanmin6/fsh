# Verification — 截图帮我回复

Date: 2026-10-15. Branch: `codex/screenshot-reply`. Baseline: main `4c6ded4`.

## Executed evidence

- Frontend: 27 unit tests, 13 native frontend contracts, TypeScript/Vite workspace build and sales build pass. Sales artifacts remain unchanged. npm audit reports zero vulnerabilities.
- Screenshot browser contract passes on Chrome at desktop 1440×1000 and mobile 390×844: upload/paste/drop, three directions, custom-only input, editing/copy, refinement using edited text, input invalidation, safe errors preserving input, linked save, permissions, and mobile overflow. No page errors.
- PHP behavior and transport contracts pass in EspoCRM 10.0.8: input/image bounds and MIME checks, malformed responses, empty screenshots, missing configuration, custom-only and refinement, fixed gpt-6.1-sol, Responses input_text/input_image, store=false, model mismatch/incomplete response rejection, HTTPS-only endpoints. New PHP syntax checks pass.
- Python: three feature contracts pass; `make verify-offline` passes 49 existing contracts plus text/media/outreach contracts. Spec Kit prerequisites pass for spec 011.
- Four real HTTP acceptance tests pass in a newly created isolated CRM/MariaDB stack on loopback 18088: authentication, ACL before provider, invalid input and missing-provider 503. Isolated volumes are removed after validation.
- The production container's existing gateway credentials successfully complete two opt-in calls using only a synthetic screenshot: three directions, followed by an English reply with Chinese translation. Both responses are accepted only when status=completed and model=gpt-6.1-sol. No real customer material or credentials are printed or committed.
- Impeccable detector: no findings. Independent finish reviewer: ship, no material fixes. Ordinary-extension documentation updated; global design remains untouched.
- Seven existing browser suites pass: unified workspace, dual AI, conversation profile, conversation sorting, translation, product creative and retry.
- `git diff --check` passes.

## Existing behavior preserved

Ported onto latest main without replacing acquisition, WeChat, Sales or other existing workflows. The remote bundled email navigation had an uncommitted “打开邮箱 · 写信” control; restored that same ACL-gated control in source before rebuilding. Deployed routes match main except the new authenticated reply-assistant endpoint.

The existing FusanheApiMiddleware normalizes non-2xx bodies to `{error:{code,requestId}}`. UI guidance uses HTTP status without exposing upstream exception text. Screenshots and temporary replies stay in page memory. Saving uses the unchanged manual-draft endpoint; this feature never sends messages.

## Deployment scope and rollback

Five runtime files: ReplyAssistant.php, Api/PostReplyAssistant.php, routes.json, workspace.js and workspace.css. Full server-side database/data/custom backups precede installation, with SHA256 manifests. A precondition checks current file hashes against the inspected snapshot before installation. Rebuild refreshes routes and app timestamp. No environment, DNS, database schema, channel flags or other modules change.

Rollback restores the three previously existing files from the application archive, removes the two newly added PHP files, and rebuilds. Preserve business data; this feature needs no database restore or migration.

## Evidence limits

Synthetic screenshots test a controlled inquiry, not all real-world layouts or languages. The tests do not certify high-load operation or every assistive technology. Runtime screenshots and server backups are intentionally excluded from Git. Production HTTP verification and final CI status are recorded below after deployment.

## Production verification

Deployed 2026-10-15 to https://crm.fsh.digital/ after verified database, data and application backups in the restricted server backup directory `reply-20261015-174045`. All five runtime hashes match the release. Public HTTPS workspace JS/CSS hashes match the tested artifacts. Rebuild succeeds. Production HTTP rejects anonymous and invalid-image requests; authenticated synthetic screenshot analysis returns three directions, and generation returns a draft plus Chinese translation through the strictly verified `gpt-6.1-sol` transport. All four CRM services remain healthy and outboundPaused remains true. No customer messages were sent.

The isolated test stack and its volumes were removed. GitHub CI is the remaining merge gate; its status is recorded in the PR.
