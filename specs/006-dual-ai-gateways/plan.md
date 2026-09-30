# Architecture and delegation

Existing EspoCRM remains authority. Keep the v1 shell and styling. Use separate adapters, namespaces, credentials and feature gates. No production deployment.

## Ownership
- Text agent: AiProvider.php, HistoryAiProvider.php, HistoryAnalysisWorker.php, text-specific new classes/API actions, WorkflowService.php, workflow.tsx, text tests. No routes/env/compose edits.
- Media agent: new Media*/Creative* backend classes/API actions and metadata, video-studio.tsx/css and related new frontend files, media tests. No routes/env/compose/shared workflow edits.
- Root: discovery, shared routes/environment/compose/bootstrap, settings shell integration, specs/version/release and integration verification.
- Acceptance agent: independent final review/tests, reports findings; no provider generation charges.

## Contract
Text env: FUSANHE_TEXT_ENABLED, FUSANHE_TEXT_API_BASE_URL, FUSANHE_TEXT_API_KEY, FUSANHE_TEXT_MODEL_GPT, FUSANHE_TEXT_MODEL_GROK, FUSANHE_TEXT_MODEL_GEMINI, FUSANHE_TEXT_DEFAULT_MODEL (choice gpt/grok/gemini), FUSANHE_TEXT_TIMEOUT. Legacy AI_* fallback only when new text channel is not explicitly enabled and no new key exists. Default base/model mappings do not activate a channel. New channel has no mock fallback.
Media env: FUSANHE_MEDIA_API_BASE_URL, FUSANHE_MEDIA_API_KEY, FUSANHE_MEDIA_IMAGE_MODEL, FUSANHE_MEDIA_VIDEO_MODEL, FUSANHE_MEDIA_ENABLED, FUSANHE_MEDIA_MAX_DAILY_JOBS, FUSANHE_MEDIA_MAX_ACTIVE_JOBS. Provider protocols require evidence; unknown capabilities disabled.
Text agent exposes TextGateway::status(), TextGateway::complete(array messages, ?string choice=null, bool json=true): array returning content, provider, model, usageTokens. Creative planning can consume this contract. Each agent reports route tuples, metadata/bootstrap needs and any additional env names before integration.

## Verification and rollback
Run offline contracts, PHP lint, TypeScript/build, browser tests and isolated EspoCRM runtime. Never use real keys in regression suites. Disable FUSANHE_MEDIA_ENABLED and remove new text env to roll back to prior adapter. Keep persisted jobs/assets; ambiguous submissions are never automatically retried.

Constitution check: specification precedes behavior; server ACL and idempotency enforced; secrets excluded; independent evidence and honest limitations required.
