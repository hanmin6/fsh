#!/usr/bin/env python3
"""Alibaba synchronization acceptance tests against the isolated test stack.

Do not point these tests at a production CRM.  Start and bootstrap the isolated
stack first (from the repository root):

  Copy-Item .env.test.example .env.test
  docker compose -p fusanhe-phase1-test --env-file .env.test -f tests/phase1-compose.yaml up -d --wait
  docker compose -p fusanhe-phase1-test --env-file .env.test -f tests/phase1-compose.yaml exec -T espocrm bin/command rebuild
  # Test-only placeholders: use the fixture values from .env.test, never production secrets.
  $env:ESPOCRM_API_URL = 'http://localhost:18080/api/v1'
  $env:ESPOCRM_ADMIN_USERNAME = 'admin'
  $env:ESPOCRM_ADMIN_PASSWORD = 'phase1-test-admin-password'
  $env:FUSANHE_AUTOMATION_TOKEN = 'phase1-test-automation-token-0123456789abcdef'
  python scripts/bootstrap.py
  $env:PYTHONUTF8 = '1'
  $env:RUN_ALIBABA_SYNC_RUNTIME = '1'
  python -m unittest tests.test_alibaba_sync_runtime -v

All data below is fictional and is tagged with a per-run stamp.  Discovery
skips this suite unless `RUN_ALIBABA_SYNC_RUNTIME=1`; once enabled, an
unreachable isolated stack is a failure.  The target URL must be loopback-only.
The suite deliberately never removes CRM records; discard the isolated stack's
named volumes when a clean test database is required.
"""
import base64
import copy
import hashlib
import json
import os
import unittest
import urllib.error
import urllib.parse
import urllib.request
import uuid


BASE = os.getenv("ESPOCRM_API_URL", "http://localhost:18080/api/v1").rstrip("/")
ADMIN_USER = os.getenv("ESPOCRM_ADMIN_USERNAME", "admin")
ADMIN_PASS = os.getenv("ESPOCRM_ADMIN_PASSWORD", "phase1-test-admin-password")
AUTO_TOKEN = os.getenv("FUSANHE_AUTOMATION_TOKEN", "phase1-test-automation-token-0123456789abcdef")
LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1"}


def assert_loopback_base_url():
    """Refuse any target other than the locally published isolated stack."""
    try:
        parsed = urllib.parse.urlparse(BASE)
        _ = parsed.port
    except ValueError as error:
        raise RuntimeError(f"ESPOCRM_API_URL is invalid: {BASE!r}") from error
    if parsed.scheme not in {"http", "https"} or parsed.hostname not in LOOPBACK_HOSTS:
        raise RuntimeError(
            "refusing Alibaba runtime tests against a non-loopback ESPOCRM_API_URL: " + BASE
        )


def api(path, method="GET", body=None, headers=None, auth=None, expect_error=False):
    request_headers = {"Content-Type": "application/json"}
    if auth:
        encoded = base64.b64encode(f"{auth[0]}:{auth[1]}".encode()).decode()
        request_headers["Authorization"] = "Basic " + encoded
    if headers:
        request_headers.update(headers)
    request = urllib.request.Request(
        BASE + path,
        None if body is None else json.dumps(body).encode(),
        request_headers,
        method=method,
    )
    return _send(request, method, path, expect_error)


def raw_api(path, raw_body, headers=None, expect_error=False):
    """Exercise Espo's JSON parser for invalid JSON as well as JSON arrays."""
    request_headers = {"Content-Type": "application/json"}
    if headers:
        request_headers.update(headers)
    request = urllib.request.Request(BASE + path, raw_body, request_headers, method="POST")
    return _send(request, "POST", path, expect_error)


def _send(request, method, path, expect_error):
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read()
            return response.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as error:
        raw = error.read()
        reason = error.headers.get("X-Status-Reason")
        try:
            data = json.loads(raw) if raw else {}
        except Exception:
            data = {"raw": raw.decode(errors="replace")}
        if not data and reason:
            data = {"message": reason}
        if not expect_error:
            raise AssertionError(f"{method} {path} -> {error.code}: {data}")
        return error.code, data


def admin_api(path, method="GET", body=None, expect_error=False):
    return api(path, method, body, auth=(ADMIN_USER, ADMIN_PASS), expect_error=expect_error)


def bootstrap_headers():
    return {"X-Automation-Token": AUTO_TOKEN}


def sp(max_size=100, where=None):
    """Espo list APIs require their filters under the searchParams parameter."""
    payload = {"maxSize": max_size}
    if where is not None:
        payload["where"] = where
    return "searchParams=" + urllib.parse.quote(json.dumps(payload, separators=(",", ":")))


class AlibabaSyncRuntime(unittest.TestCase):
    """Runtime coverage for the inbound-only Alibaba connector boundary."""

    @classmethod
    def setUpClass(cls):
        assert_loopback_base_url()
        if os.getenv("RUN_ALIBABA_SYNC_RUNTIME") != "1":
            raise unittest.SkipTest("set RUN_ALIBABA_SYNC_RUNTIME=1 to execute isolated Alibaba runtime tests")
        cls.stamp = uuid.uuid4().hex
        try:
            _, app = admin_api("/App/user")
        except urllib.error.URLError as error:
            raise AssertionError(f"isolated CRM stack is not reachable at {BASE}: {error.reason}") from error
        cls.admin_id = app["user"]["id"]
        cls.agent_key = f"ali-runtime-{cls.stamp[:20]}"
        registration, cls.agent_headers = cls.register_agent(
            cls.agent_key, capabilities=["Alibaba"], mode="real"
        )
        if not registration.get("credentialIssued") or not registration.get("agentToken"):
            raise AssertionError("new Alibaba agent must receive its one-time credential")

    @classmethod
    def register_agent(cls, agent_key, **extra):
        payload = {"agentKey": agent_key, "mode": "real", "capabilities": ["Alibaba"]}
        payload.update(extra)
        _, registration = api(
            "/Fusanhe/agent/register", "POST", payload, headers=bootstrap_headers()
        )
        token = registration.get("agentToken")
        headers = {"X-Agent-Key": agent_key}
        if token:
            headers["X-Agent-Token"] = token
        return registration, headers

    def sync(self, payload, headers=None, expect_error=False):
        return api(
            "/Fusanhe/alibaba/sync",
            "POST",
            payload,
            headers=self.agent_headers if headers is None else headers,
            expect_error=expect_error,
        )

    def request_id(self, label):
        return f"ali-{self.stamp[:18]}-{label}"

    def inquiry_id(self, label):
        return f"INQ-{self.stamp[:18]}-{label}"

    def message(self, external_id, direction, sequence, body):
        fixture_id = f"{self.stamp[:18]}-{external_id}"
        return {
            "externalId": fixture_id,
            "direction": direction,
            "body": body,
            "senderName": "Fictional Buyer" if direction == "inbound" else "Fictional Seller",
            "senderExternalId": f"{self.stamp[:18]}-{direction}-sender-{external_id}",
            "sentAt": f"2026-09-20T10:{sequence:02d}:00Z",
            "sourceTimestampRaw": f"Alibaba fixture timestamp {sequence}",
            "timestampConfidence": "high",
            "sourceSequence": sequence,
            "messageType": "initialInquiry" if sequence == 1 else "chat",
        }

    def payload(self, label, *, inquiry_id=None, sync_mode="backfill", final_batch=None,
                unread_count=0, messages=None):
        inquiry_id = inquiry_id or self.inquiry_id(label)
        phone_seed = int(hashlib.sha256(inquiry_id.encode()).hexdigest(), 16) % 10**10
        payload = {
            "requestId": self.request_id(label),
            "jobId": f"job-{self.stamp[:18]}-{label}",
            "accountHandle": f"fixture-shop-{self.stamp[:18]}",
            "syncMode": sync_mode,
            "conversation": {
                "inquiryId": inquiry_id,
                "buyerExternalId": f"buyer-{inquiry_id}",
                "buyerName": "Fictional Buyer LLC",
                "buyerEmail": f"buyer.{inquiry_id.lower()}@fixture.invalid",
                "buyerPhone": f"+1555{phone_seed:010d}",
                "country": "Fixtureland",
                "subject": "Fictional hydraulic fitting inquiry",
                "createdAtRaw": "2026-09-20 10:00:00 Alibaba",
                "updatedAtRaw": "2026-09-20 10:30:00 Alibaba",
                "unreadCount": unread_count,
            },
            "messages": messages or [],
        }
        if final_batch is not None:
            payload["finalBatch"] = final_batch
        return payload

    def exact_list(self, entity, where):
        _, data = admin_api(f"/{entity}?" + sp(where=where))
        return data

    def conversation_records(self, inquiry_id):
        return self.exact_list(
            "ExternalConversation",
            [{"type": "equals", "attribute": "externalId", "value": inquiry_id}],
        )

    def assert_no_automation_side_effects(self, conversation_id):
        where = [{"type": "equals", "attribute": "conversationId", "value": conversation_id}]
        self.assertEqual(self.exact_list("AIReplyDraft", where)["total"], 0)
        self.assertEqual(self.exact_list("OutboundTask", where)["total"], 0)

    def assert_error_response(self, status, data, expected_status):
        self.assertEqual(status, expected_status)
        self.assertIsInstance(data, dict, "error responses must be JSON objects")
        self.assertTrue(data, "error responses must not be empty")
        self.assertTrue(
            any(data.get(key) for key in ("error", "message", "errors", "raw")),
            f"error response must include error or message details: {data}",
        )

    def test_backfill_is_payload_bound_and_finalization_is_explicit(self):
        inquiry_id = self.inquiry_id("backfill")
        messages = [
            self.message("buyer-initial", "inbound", 1, "Please quote fictional fittings."),
            self.message("seller-reply", "outbound", 2, "Fictional quote sent."),
        ]
        first_payload = self.payload(
            "backfill-first", inquiry_id=inquiry_id, final_batch=False,
            unread_count=7, messages=messages,
        )
        _, first = self.sync(first_payload)
        self.assertTrue(first["createdConversation"])
        self.assertTrue(first["identityId"])
        self.assertTrue(first["createdLead"])
        self.assertTrue(first["leadId"])
        self.assertEqual(first["createdMessages"], 2)
        self.assertFalse(first["finalized"])

        _, before_final = admin_api(f"/ExternalConversation/{first['conversationId']}")
        self.assertFalse(before_final.get("lastSourceSyncAt"))
        self.assertFalse(before_final.get("backfillCompletedAt"))

        lead_where = [
            {"type": "equals", "attribute": "id", "value": first["leadId"]},
            {"type": "contains", "attribute": "description", "value": inquiry_id},
        ]
        initially_related_leads = self.exact_list("Lead", lead_where)
        self.assertEqual(initially_related_leads["total"], 1)
        self.assertEqual(len(initially_related_leads["list"]), 1)
        self.assertEqual(initially_related_leads["list"][0]["id"], first["leadId"])

        _, replay = self.sync(first_payload)
        self.assertEqual(replay, first, "same request ID and payload must replay exactly")
        altered = copy.deepcopy(first_payload)
        altered["messages"][0]["body"] = "Changed body must conflict."
        code, error = self.sync(altered, expect_error=True)
        self.assert_error_response(code, error, 409)

        final_payload = self.payload(
            "backfill-final", inquiry_id=inquiry_id, final_batch=True,
            unread_count=7, messages=[
                messages[1],
                self.message("seller-followup", "outbound", 3, "A fictional follow-up quote."),
            ],
        )
        _, final = self.sync(final_payload)
        self.assertTrue(final["finalized"])
        self.assertFalse(final["createdConversation"])
        self.assertEqual(final["createdMessages"], 1)
        self.assertEqual(final["deduplicatedMessages"], 1)

        conversations = self.conversation_records(inquiry_id)
        self.assertEqual(conversations["total"], 1)
        conversation = conversations["list"][0]
        self.assertEqual(conversation["id"], first["conversationId"])
        self.assertEqual(conversation["identityId"], first["identityId"])
        self.assertEqual(conversation["leadId"], first["leadId"])
        self.assertEqual(conversation["status"], "replied")
        self.assertEqual(conversation["unreadCount"], 7)
        self.assertTrue(conversation.get("backfillCompletedAt"))

        _, identity = admin_api(f"/ExternalIdentity/{first['identityId']}")
        _, lead = admin_api(f"/Lead/{first['leadId']}")
        self.assertEqual(identity["id"], first["identityId"])
        self.assertEqual(identity["leadId"], first["leadId"])
        self.assertEqual(lead["id"], first["leadId"])
        related_leads = self.exact_list("Lead", lead_where)
        self.assertEqual(related_leads["total"], 1, "replayed backfill must not create another related Lead")
        self.assertEqual(len(related_leads["list"]), 1)
        self.assertEqual(related_leads["list"][0]["id"], first["leadId"])
        message_rows = self.exact_list(
            "ExternalMessage",
            [{"type": "equals", "attribute": "conversationId", "value": first["conversationId"]}],
        )
        self.assertEqual(message_rows["total"], 3)
        self.assertEqual(
            {row["externalId"] for row in message_rows["list"]},
            {message["externalId"] for message in messages} | {final_payload["messages"][1]["externalId"]},
        )
        self.assert_no_automation_side_effects(first["conversationId"])

    def test_empty_final_backfill_marks_source_sync(self):
        inquiry_id = self.inquiry_id("empty-final")
        _, result = self.sync(self.payload(
            "empty-final", inquiry_id=inquiry_id, final_batch=True, messages=[],
        ))
        self.assertTrue(result["finalized"])
        self.assertEqual(result["createdMessages"], 0)
        _, conversation = admin_api(f"/ExternalConversation/{result['conversationId']}")
        self.assertEqual(conversation["externalId"], inquiry_id)
        self.assertTrue(conversation.get("lastSourceSyncAt"))
        self.assertTrue(conversation.get("backfillCompletedAt"))

    def test_sync_validation_rejects_invalid_batches_without_partial_writes(self):
        def invalid_payload(label):
            return self.payload(
                label, final_batch=True,
                messages=[self.message(f"{label}-message", "inbound", 1, "Validation fixture.")],
            )

        cases = []
        bad_final = invalid_payload("invalid-final-batch")
        bad_final["finalBatch"] = "true"
        cases.append(("finalBatch", bad_final))
        bad_name = invalid_payload("invalid-buyer-name")
        bad_name["conversation"]["buyerName"] = "n" * 256
        cases.append(("buyerName", bad_name))
        bad_external_id = invalid_payload("invalid-external-id")
        bad_external_id["messages"][0]["externalId"] = f"{self.stamp}-" + "x" * 192
        cases.append(("externalId", bad_external_id))
        bad_body = invalid_payload("invalid-body")
        bad_body["messages"][0]["body"] = "x" * 200001
        cases.append(("body", bad_body))
        for field, value in (("direction", "sideways"), ("timestampConfidence", "unknown"),
                             ("messageType", "other"), ("sourceSequence", 0)):
            invalid = invalid_payload(f"invalid-{field}")
            invalid["messages"][0][field] = value
            cases.append((field, invalid))

        for label, payload in cases:
            with self.subTest(label=label):
                code, error = self.sync(payload, expect_error=True)
                self.assert_error_response(code, error, 400)

        inquiry_id = self.inquiry_id("rollback")
        first_message = self.message("rollback-valid", "inbound", 1, "Must not persist.")
        second_message = self.message("rollback-invalid", "inbound", 2, "Invalid after valid.")
        second_message["direction"] = "invalid"
        rollback = self.payload(
            "rollback", inquiry_id=inquiry_id, final_batch=True,
            messages=[first_message, second_message],
        )
        code, error = self.sync(rollback, expect_error=True)
        self.assert_error_response(code, error, 400)
        self.assertEqual(self.conversation_records(inquiry_id)["total"], 0)
        persisted = self.exact_list(
            "ExternalMessage",
            [{"type": "equals", "attribute": "externalId", "value": first_message["externalId"]}],
        )
        self.assertEqual(persisted["total"], 0, "a rejected batch must not persist its preceding valid message")

    def test_incremental_sync_deduplicates_and_never_queues_a_reply(self):
        inquiry_id = self.inquiry_id("incremental")
        _, initial = self.sync(self.payload(
            "incremental-seed", inquiry_id=inquiry_id, final_batch=True, unread_count=1,
            messages=[self.message("seed-inbound", "inbound", 1, "Seed inquiry.")],
        ))

        inbound = self.payload(
            "incremental-inbound", inquiry_id=inquiry_id, sync_mode="incremental", unread_count=5,
            messages=[self.message("followup-inbound", "inbound", 2, "Please answer today.")],
        )
        _, received = self.sync(inbound)
        self.assertTrue(received["finalized"])
        self.assertEqual(received["createdMessages"], 1)
        _, pending = admin_api(f"/ExternalConversation/{initial['conversationId']}")
        self.assertEqual(pending["status"], "pending")
        self.assertEqual(pending["unreadCount"], 5)

        duplicate = copy.deepcopy(inbound)
        duplicate["requestId"] = self.request_id("incremental-duplicate")
        duplicate["jobId"] = f"job-{self.stamp[:18]}-incremental-duplicate"
        _, duplicate_result = self.sync(duplicate)
        self.assertEqual(duplicate_result["createdMessages"], 0)
        self.assertEqual(duplicate_result["deduplicatedMessages"], 1)

        _, outbound = self.sync(self.payload(
            "incremental-outbound", inquiry_id=inquiry_id, sync_mode="incremental", unread_count=0,
            messages=[self.message("followup-outbound", "outbound", 3, "A fictional answer.")],
        ))
        self.assertTrue(outbound["finalized"])
        _, replied = admin_api(f"/ExternalConversation/{initial['conversationId']}")
        self.assertEqual(replied["status"], "replied")
        self.assertEqual(replied["unreadCount"], 0)
        messages = self.exact_list(
            "ExternalMessage",
            [{"type": "equals", "attribute": "conversationId", "value": initial["conversationId"]}],
        )
        self.assertEqual(messages["total"], 3)
        self.assert_no_automation_side_effects(initial["conversationId"])

    def test_sync_authentication_capability_and_audit_actor_bound_to_headers(self):
        valid = self.payload(
            "auth-actor", final_batch=True,
            messages=[self.message("auth-message", "inbound", 1, "Audit actor fixture.")],
        )
        for headers in ({}, {"X-Agent-Key": self.agent_key, "X-Agent-Token": "wrong-token"}, bootstrap_headers()):
            code, error = self.sync(valid, headers=headers, expect_error=True)
            self.assert_error_response(code, error, 403)

        no_cap_key = f"ali-no-cap-{self.stamp[:18]}"
        _, no_cap_headers = self.register_agent(no_cap_key, capabilities=["Website"], mode="real")
        code, error = self.sync(self.payload(
            "auth-no-cap", final_batch=True,
            messages=[self.message("no-cap-message", "inbound", 1, "No capability fixture.")],
        ), headers=no_cap_headers, expect_error=True)
        self.assert_error_response(code, error, 403)

        revoked_key = f"ali-revoked-{self.stamp[:18]}"
        revoked_registration, revoked_headers = self.register_agent(revoked_key)
        admin_api(f"/AutomationAgent/{revoked_registration['agentId']}", "PATCH", {"credentialStatus": "revoked"})
        code, error = self.sync(self.payload(
            "auth-revoked", final_batch=True,
            messages=[self.message("revoked-message", "inbound", 1, "Revoked fixture.")],
        ), headers=revoked_headers, expect_error=True)
        self.assert_error_response(code, error, 403)

        missing_hash_key = f"ali-no-hash-{self.stamp[:18]}"
        admin_api("/AutomationAgent", "POST", {
            "name": missing_hash_key,
            "agentKey": missing_hash_key,
            "mode": "real",
            "status": "online",
            "capabilities": ["Alibaba"],
            "credentialStatus": "active",
        })
        code, error = self.sync(self.payload(
            "auth-no-hash", final_batch=True,
            messages=[self.message("no-hash-message", "inbound", 1, "Missing hash fixture.")],
        ), headers={"X-Agent-Key": missing_hash_key, "X-Agent-Token": "not-a-credential"}, expect_error=True)
        self.assert_error_response(code, error, 403)

        spoofed = copy.deepcopy(valid)
        spoofed["agentKey"] = "body-value-must-not-select-the-actor"
        _, result = self.sync(spoofed)
        audit = self.exact_list(
            "AutomationAudit",
            [{"type": "equals", "attribute": "requestId", "value": result["requestId"]}],
        )
        self.assertEqual(audit["total"], 1)
        self.assertEqual(audit["list"][0]["actorId"], self.agent_key)

    def test_agent_credentials_issue_once_rotate_and_reject_old_token(self):
        key = f"ali-credential-{self.stamp[:18]}"
        first, first_headers = self.register_agent(key)
        self.assertTrue(first["credentialIssued"])
        self.assertIn("X-Agent-Token", first_headers)

        ordinary, ordinary_headers = self.register_agent(key)
        self.assertFalse(ordinary["credentialIssued"])
        self.assertNotIn("agentToken", ordinary)
        self.assertNotIn("X-Agent-Token", ordinary_headers)

        rotated, rotated_headers = self.register_agent(key, rotateCredential=True)
        self.assertTrue(rotated["credentialIssued"])
        self.assertIn("X-Agent-Token", rotated_headers)
        code, error = self.sync(self.payload(
            "credential-old", final_batch=True,
            messages=[self.message("old-token-message", "inbound", 1, "Old token fixture.")],
        ), headers=first_headers, expect_error=True)
        self.assert_error_response(code, error, 403)

        _, fresh = self.sync(self.payload(
            "credential-new", final_batch=True,
            messages=[self.message("new-token-message", "inbound", 1, "New token fixture.")],
        ), headers=rotated_headers)
        self.assertEqual(fresh["requestId"], self.request_id("credential-new"))

    def test_sync_rejects_non_object_and_malformed_json_bodies(self):
        code, error = raw_api("/Fusanhe/alibaba/sync", b"[]", headers=self.agent_headers, expect_error=True)
        self.assert_error_response(code, error, 400)
        code, error = raw_api("/Fusanhe/alibaba/sync", b'{"requestId":', headers=self.agent_headers, expect_error=True)
        self.assert_error_response(code, error, 400)


if __name__ == "__main__":
    unittest.main()
