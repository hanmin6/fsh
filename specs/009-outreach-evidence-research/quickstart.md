# Quickstart: CRM 触达证据与 AI 背调

1. Rebuild EspoCRM after adding the metadata and routes:

   ```bash
   docker compose exec -T espocrm bin/command rebuild
   python3 scripts/bootstrap.py
   ```

2. Create an evidence record through the CRM API. The screenshot must be a bounded PNG, JPEG or WebP data URL. The endpoint only records evidence and never sends a message:

   ```json
   {
     "idempotencyKey": "social-20261003-demo-0001",
     "targetType": "Lead",
     "targetId": "<lead-id>",
     "channelType": "LinkedIn",
     "profileUrl": "https://www.linkedin.com/in/example",
     "externalMessageId": "platform-message-1",
     "messageBody": "Hello, here is a short product introduction.",
     "sendStatus": "sent",
    "sentAt": "2026-10-03T08:00:00Z",
     "customerSnapshot": {"name": "Example Buyer", "company": "Example Foods", "role": "Purchasing"},
     "screenshotDataUrl": "data:image/png;base64,..."
   }
   ```

3. Open the customer in the CRM workbench and select **主动触达**. The record displays the message facts and a private screenshot preview.

4. Select **开始 AI 背调**. The configured text gateway performs bounded public web search and stores the report, evidence URLs, model and prompt version. If the gateway is unavailable, the evidence remains intact and the research status becomes `failed`.

This phase does not require a Muse account and does not create `OutboundTask` records.
