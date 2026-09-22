#!/usr/bin/env python3
"""One-shot simulator for the Guangzhou Windows sender. Uses stdlib only."""

import json
import os
import sys
import urllib.request


base = os.getenv("ESPOCRM_API_URL", "http://localhost:8080/api/v1").rstrip("/")
bootstrap_token = os.getenv("FUSANHE_AUTOMATION_TOKEN", "")
agent_key = os.getenv("FUSANHE_AGENT_KEY", "guangzhou-demo-agent")
agent_token = os.getenv("FUSANHE_AGENT_TOKEN", "")
rotate_agent_token = os.getenv("FUSANHE_ROTATE_AGENT_TOKEN", "") == "1"
capabilities = [
    capability
    for capability in os.getenv(
        "FUSANHE_AGENT_CAPABILITIES", "Alibaba,MadeInChina,Website,Email,WhatsApp,Other"
    ).split(",")
    if capability
]


def post(path, data, headers):
    request = urllib.request.Request(
        base + path,
        json.dumps(data).encode(),
        headers,
        method="POST",
    )
    with urllib.request.urlopen(request) as response:
        return json.load(response)


if not agent_token:
    if not rotate_agent_token:
        sys.exit(
            "Configure FUSANHE_AGENT_TOKEN, or explicitly set "
            "FUSANHE_ROTATE_AGENT_TOKEN=1 with FUSANHE_AUTOMATION_TOKEN."
        )
    if not bootstrap_token:
        sys.exit("FUSANHE_ROTATE_AGENT_TOKEN=1 requires FUSANHE_AUTOMATION_TOKEN.")
    bootstrap_headers = {
        "Content-Type": "application/json",
        "X-Automation-Token": bootstrap_token,
    }
    registration = post(
        "/Fusanhe/agent/register",
        {
            "agentKey": agent_key,
            "name": "广州模拟执行端",
            "mode": "mock",
            "capabilities": capabilities,
            "rotateCredential": True,
        },
        bootstrap_headers,
    )
    agent_token = registration.get("agentToken")
    if not registration.get("credentialIssued") or not isinstance(agent_token, str) or not agent_token:
        sys.exit("Explicit agent credential rotation did not issue a credential.")

agent_headers = {
    "Content-Type": "application/json",
    "X-Agent-Key": agent_key,
    "X-Agent-Token": agent_token,
}
# Confirm the persisted per-Agent credential before attempting to claim work.
post("/Fusanhe/agent/heartbeat", {}, agent_headers)
claimed = post("/Fusanhe/agent/claim", {}, agent_headers)
if claimed.get("paused"):
    print("Outbound is globally paused.")
    sys.exit(2)
task = claimed.get("task")
if not task:
    print("No pending task.")
    sys.exit(0)
post(f"/Fusanhe/agent/task/{task['id']}/sending", {}, agent_headers)
result = post(
    f"/Fusanhe/agent/task/{task['id']}/result",
    {"success": True, "platformMessageId": "MOCK-" + task["id"]},
    agent_headers,
)
print(json.dumps({"claimed": task["id"], "result": result}, ensure_ascii=False))
