# Dual AI gateways (CRM Web 1.1)

## Requirements
- R1: Two isolated server-side channels: APIMonth text; TokenDance image/video. Credentials never reach clients, Git, prompts, logs or tests.
- R2: Catalog-verified model IDs. Display choices GPT-6.1 Sol, Grok 4.7 and Gemini 3.8 Flash do not imply availability. Unavailable models remain unavailable; no substitutions without explicit selection.
- R3: Existing reply and privacy-preserving history workflows use text adapter; users can select a configured model. Persist actual provider/model/usage. Real requests never silently become mock successes.
- R4: Creative options use text; a selected option can submit a media job only for a verified supported capability. Source uploads, persisted owner-scoped jobs, polling, preview/download and associations preserve ACL. Demo remains synthetic and isolated.
- R5: Paid media submission is idempotent; ambiguous submission failures require reconciliation rather than blind resubmission. Bounded concurrency/daily request budget; unknown monetary costs are labeled unknown.
- R6: Outbound human approval/global stop remain intact. Generated content never auto-sends.
- R7: Health/configuration surfaces report honest availability; no raw upstream errors. Rollback retains jobs and assets.

## Scope clarification
User selected “暂不启用图片生成，先接好视频”. Static image generation remains disabled; image uploads remain available as source materials. Video uses minimax-h3-max.

## Known gaps before implementation
Model IDs and media endpoint protocols are unverified. The user-supplied minimax-h3-max alias may not be a media model. Integration must fail closed where provider evidence is absent.

## Acceptance
Meaningful provider fake-transport contracts, ACL and retry tests, existing regression/build checks, runtime/browser creative workflows, secret isolation review by independent agent, and read-only live catalogs. External unsupported capabilities are recorded explicitly.
