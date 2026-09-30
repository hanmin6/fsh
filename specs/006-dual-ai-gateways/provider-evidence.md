# Provider evidence — 2026-09-30

No credentials or customer data are contained here. Catalog requests authenticated with locally ignored server-only configuration.

## Text / APIMonth
GET https://gw.apimonth.com/v1/models: HTTP 200, 40 model IDs. Exact requested IDs present: gpt-6.1-sol, grok-4.7, gemini-3.8-flash.

Synthetic JSON-only smoke:
- grok-4.7: POST /chat/completions HTTP 200, returned model grok-4.7, valid JSON, 1334 total tokens.
- gemini-3.8-flash: POST /chat/completions HTTP 200, returned model gemini-3.8-flash, valid JSON, 161 total tokens.
- gpt-6.1-sol: /chat/completions HTTP 400 unsupported_protocol. Provider explicitly requires Responses API. POST /responses then HTTP 200, status completed, output[].content[].type=output_text, valid JSON, model gpt-6.1-sol, 36 total tokens.

No automatic model fallback or paid request retry. This is relay behavior, not a claim about official model availability.

## Media / TokenDance
GET https://tokendance.space/gateway/v1/models: HTTP 200, 106 model IDs.
- minimax-h3-max: supported_protocols=[minimax:video_generation_v2]. Video only, text/first-frame/last-frame, 480P/768P, 5–15 seconds. Not a static image model.
- seedream-5.0-lite: supported_protocols include openai:image-generations and ark:image-generations. User explicitly selected no static-image generation in this release; image model remains empty and capability disabled.

Public protocol sources:
- https://tokendance.space/docs/protocol-minimax-video-generation-v2.md
- https://tokendance.space/docs/minimax-video-generation.md
- https://tokendance.space/docs/protocol-openai-image-generations.md

Video POST /gateway/minimax/v2/video_generation returns task_id. GET /gateway/minimax/v2/query/video_generation/{id} returns task.status and task.content.url. Image-source requests must omit ratio; source URL must be publicly reachable. No documented support for base64/data URI or provider-side idempotency. Result URL expires after 24 hours; persist files promptly. Images POST /gateway/v1/images/generations uses model,prompt,n=1,size; data[].url.

Video synthetic smoke: POST V2 HTTP 200 with task_id, minimax-h3-max / 480P / 5 seconds / text-only / 16:9. Query HTTP 200, status succeeded with content.url. Downloaded 804358-byte MP4 (ftyp signature), locally retained as private test evidence. Chrome playback validation: no media error; 832×480, duration 5.184 seconds. No image generation was called. Independent acceptance evidence is separate.
