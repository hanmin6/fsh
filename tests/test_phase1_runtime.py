#!/usr/bin/env python3
"""Phase 1 runtime verification against the isolated test stack.

Requires the environment started with:
  docker compose -p fusanhe-phase1-test --env-file .env.test -f tests/phase1-compose.yaml up -d --wait
  docker compose -p fusanhe-phase1-test --env-file .env.test -f tests/phase1-compose.yaml exec -T espocrm bin/command rebuild
  set -a; . ./.env.test; set +a; ESPOCRM_API_URL=http://localhost:18080/api/v1 python3 scripts/bootstrap.py

All data is fictional demo data created by these tests themselves.

Run order:
  1. With FUSANHE_OUTBOUND_PAUSED=true:
       python3 -m unittest tests.test_phase1_runtime.Phase1Runtime -v
  2. Flip FUSANHE_OUTBOUND_PAUSED=false in .env.test and recreate espocrm:
       docker compose -p fusanhe-phase1-test --env-file .env.test -f tests/phase1-compose.yaml up -d --force-recreate espocrm
     then:
       python3 -m unittest tests.test_phase1_runtime.Phase1SendLoop -v
"""
import base64
import json
import os
import time
import unittest
import urllib.error
import urllib.parse
import urllib.request

BASE = os.getenv("ESPOCRM_API_URL", "http://localhost:18080/api/v1").rstrip("/")
ADMIN_USER = os.getenv("ESPOCRM_ADMIN_USERNAME", "admin")
ADMIN_PASS = os.getenv("ESPOCRM_ADMIN_PASSWORD", "phase1-test-admin-password")
AUTO_TOKEN = os.getenv("FUSANHE_AUTOMATION_TOKEN", "phase1-test-automation-token-0123456789abcdef")


def api(path, method="GET", body=None, headers=None, auth=None, expect_error=False):
    h = {"Content-Type": "application/json"}
    if auth:
        h["Authorization"] = "Basic " + base64.b64encode(f"{auth[0]}:{auth[1]}".encode()).decode()
    if headers:
        h.update(headers)
    req = urllib.request.Request(
        BASE + path,
        None if body is None else json.dumps(body).encode(),
        h,
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read()
            return resp.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        payload = e.read()
        try:
            data = json.loads(payload) if payload else {}
        except Exception:
            data = {"raw": payload.decode(errors="replace")}
        if not expect_error:
            raise AssertionError(f"{method} {path} -> {e.code}: {data}")
        return e.code, data


def admin_api(path, method="GET", body=None, expect_error=False):
    return api(path, method, body, auth=(ADMIN_USER, ADMIN_PASS), expect_error=expect_error)


def sp(max_size=100, where=None, text_filter=None):
    """EspoCRM 10 ignores a JSON-string `where` query param; list queries must
    use the `searchParams` JSON parameter instead."""
    payload = {"maxSize": max_size}
    if where is not None:
        payload["where"] = where
    if text_filter:
        payload["textFilter"] = text_filter
    return "searchParams=" + urllib.parse.quote(json.dumps(payload, separators=(",", ":")))


class Phase1Runtime(unittest.TestCase):
    """Acceptance scenarios run with outbound globally paused (production default)."""

    @classmethod
    def setUpClass(cls):
        cls.stamp = str(int(time.time()))
        _, app = admin_api("/App/user")
        cls.admin_id = app["user"]["id"]
        cls.sales_login = (f"sales-{cls.stamp}", "Phase1-Sales-Pass-1")
        cls.sales_id = cls._make_sales_user(cls)

    def intake(self, conv_ext, msg_ext, **extra):
        payload = {
            "channelType": "Website",
            "conversationExternalId": conv_ext,
            "messageExternalId": msg_ext,
            "body": extra.pop("body", "Hello, I need information about hydraulic fittings."),
        }
        payload.update(extra)
        return admin_api("/Fusanhe/mock/intake", "POST", payload)

    def _make_sales_user(self):
        _, data = admin_api("/Role?maxSize=100")
        role_id = None
        for r in data.get("list", []):
            if r.get("name") == "业务员":
                role_id = r["id"]
        assert role_id, "业务员 role must exist (run scripts/bootstrap.py first)"
        _, user = admin_api("/User", "POST", {
            "userName": self.sales_login[0],
            "lastName": "Phase1 Sales",
            "password": self.sales_login[1],
            "isActive": True,
            "rolesIds": [role_id],
        })
        return user["id"]

    def sales_api(self, path, method="GET", body=None, expect_error=False):
        return api(path, method, body, auth=self.sales_login, expect_error=expect_error)

    # ---- 1. new visitor: reception without automatic Lead ----

    def test_01_new_visitor_does_not_create_lead(self):
        company = f"Visitor Co {self.stamp}"
        _, conv = self.intake(
            f"CONV-{self.stamp}-A", f"MSG-{self.stamp}-A1",
            senderName="Alice Visitor", company=company, country="Germany",
            email=f"alice.{self.stamp}@visitor.example", externalUserId=f"uid-alice-{self.stamp}",
        )
        self.assertFalse(conv["createdLead"], "intake must not auto-create a Lead")
        self.assertTrue(conv["identityId"])
        self.assertTrue(conv["needsManualMatch"])
        _, leads = admin_api("/Lead?" + sp(text_filter=company))
        self.assertEqual(len(leads["list"]), 0, "no Lead may exist for the visitor company")

    # ---- 2. duplicate import stays idempotent ----

    def test_02_duplicate_import_is_idempotent(self):
        conv_ext = f"CONV-{self.stamp}-B"
        payload = {
            "channelType": "Website",
            "conversationExternalId": conv_ext,
            "messageExternalId": f"MSG-{self.stamp}-B1",
            "body": "Duplicate import check.",
            "email": f"dup.{self.stamp}@visitor.example",
            "externalUserId": f"uid-dup-{self.stamp}",
        }
        _, first = admin_api("/Fusanhe/mock/intake", "POST", payload)
        _, second = admin_api("/Fusanhe/mock/intake", "POST", payload)
        self.assertTrue(second["deduplicated"])
        self.assertEqual(first["conversationId"], second["conversationId"])
        self.assertEqual(first["messageId"], second["messageId"])
        _, messages = admin_api("/ExternalMessage?" + sp(where=[
            {"type": "equals", "attribute": "conversationId", "value": first["conversationId"]},
        ]))
        self.assertEqual(len(messages["list"]), 1, "duplicate event must not add a second message")

    # ---- 3. same external user id on two channel accounts must not merge ----

    def test_03_same_external_id_different_channel_accounts_do_not_merge(self):
        uid = f"uid-shared-{self.stamp}"
        _, first = self.intake(
            f"CONV-{self.stamp}-C1", f"MSG-{self.stamp}-C1",
            externalUserId=uid, email=f"c1.{self.stamp}@visitor.example", accountHandle="shop-one",
        )
        _, second = self.intake(
            f"CONV-{self.stamp}-C2", f"MSG-{self.stamp}-C2",
            externalUserId=uid, email=f"c2.{self.stamp}@visitor.example", accountHandle="shop-two",
        )
        self.assertNotEqual(first["identityId"], second["identityId"],
                            "channel account instance must be part of identity uniqueness")
        self.assertNotEqual(first["conversationId"], second["conversationId"])
        _, identities = admin_api("/ExternalIdentity?" + sp(where=[
            {"type": "equals", "attribute": "externalUserId", "value": uid},
        ]))
        self.assertEqual(len(identities["list"]), 2)

    # ---- 4/5. candidates, ACL filtering, manual confirmation, two-way navigation,
    # ---- 6. idempotent handoff, 7. owner vs attendant ----

    def test_04_to_07_identity_handoff_and_roles(self):
        email = f"match.{self.stamp}@visitor.example"
        _, match = self.intake(
            f"CONV-{self.stamp}-D", f"MSG-{self.stamp}-D1",
            senderName="Matchy Visitor", email=email, externalUserId=f"uid-match-{self.stamp}",
        )
        _, account = admin_api("/Account", "POST", {
            "name": f"Matched Account {self.stamp}",
            "emailAddress": email,
            "assignedUserId": self.admin_id,
        })

        # weak evidence only: company/name must not produce candidates
        _, weak = self.intake(
            f"CONV-{self.stamp}-E", f"MSG-{self.stamp}-E1",
            senderName="Weak Evidence", company=f"Some Company {self.stamp}",
        )
        _, weak_cands = admin_api(
            f"/Fusanhe/identity/{weak['identityId']}/candidates?conversationId={weak['conversationId']}"
        )
        self.assertEqual(weak_cands["candidates"], [], "company/name-only matches must not be proposed")

        # out-of-scope leak check: conversation owned by the salesperson, account owned by admin
        _, scoped = self.intake(
            f"CONV-{self.stamp}-E2", f"MSG-{self.stamp}-E2",
            email=email, externalUserId=f"uid-scoped-{self.stamp}",
        )
        admin_api(f"/ExternalConversation/{scoped['conversationId']}", "PATCH", {"assignedUserId": self.sales_id})
        _, sales_view = self.sales_api(
            f"/Fusanhe/identity/{scoped['identityId']}/candidates?conversationId={scoped['conversationId']}"
        )
        self.assertEqual(sales_view["candidates"], [],
                         "candidates outside the user's data scope must not leak")
        _, admin_view = admin_api(
            f"/Fusanhe/identity/{scoped['identityId']}/candidates?conversationId={scoped['conversationId']}"
        )
        self.assertEqual(len(admin_view["candidates"]), 1)
        self.assertEqual(admin_view["candidates"][0]["type"], "Account")

        # admin confirms the link on the first conversation
        conv_id = match["conversationId"]
        identity_id = match["identityId"]
        _, linked = admin_api(f"/Fusanhe/identity/{identity_id}/link", "POST", {
            "conversationId": conv_id, "targetType": "Account", "targetId": account["id"],
        })
        self.assertEqual(linked["linkStatus"], "confirmed")
        _, conv_after = admin_api(f"/ExternalConversation/{conv_id}")
        self.assertEqual(conv_after["accountId"], account["id"], "conversation links to the confirmed customer")
        self.assertFalse(conv_after["needsManualMatch"])

        # two-way navigation: customer detail query finds the conversation
        _, by_account = admin_api("/ExternalConversation?" + sp(where=[
            {"type": "equals", "attribute": "accountId", "value": account["id"]},
        ]))
        self.assertTrue(any(c["id"] == conv_id for c in by_account["list"]))

        # 6. handoff is idempotent: duplicate request returns the same business result
        handoff_body = {
            "summary": f"Handoff summary {self.stamp}",
            "assignedUserId": self.admin_id,
            "dateEnd": "2099-01-31",
        }
        _, task1 = admin_api(f"/Fusanhe/conversation/{conv_id}/handoff", "POST", handoff_body)
        _, task2 = admin_api(f"/Fusanhe/conversation/{conv_id}/handoff", "POST", handoff_body)
        self.assertEqual(task1["taskId"], task2["taskId"], "duplicate handoff returns the same task")
        self.assertFalse(task1["deduplicated"])
        self.assertTrue(task2["deduplicated"])
        _, task_detail = admin_api(f"/Task/{task1['taskId']}")
        self.assertEqual(task_detail["parentType"], "ExternalConversation")
        self.assertEqual(task_detail["parentId"], conv_id, "task links back to the source conversation")
        self.assertIn(handoff_body["summary"], task_detail["description"] or "")

        # 7. customer owner and conversation attendant are independent
        admin_api(f"/ExternalConversation/{conv_id}", "PATCH", {"assignedUserId": self.sales_id})
        _, conv_final = admin_api(f"/ExternalConversation/{conv_id}")
        _, account_after = admin_api(f"/Account/{account['id']}")
        self.assertEqual(conv_final["assignedUserId"], self.sales_id, "attendant can differ from customer owner")
        self.assertEqual(account_after["assignedUserId"], self.admin_id, "customer owner unchanged")

    # ---- 8. permission walls ----

    def test_08_permission_walls(self):
        _, conv = self.intake(
            f"CONV-{self.stamp}-F", f"MSG-{self.stamp}-F1",
            email=f"perm.{self.stamp}@visitor.example", externalUserId=f"uid-perm-{self.stamp}",
        )
        conv_id = conv["conversationId"]
        identity_id = conv["identityId"]

        code, _ = self.sales_api(f"/Fusanhe/identity/{identity_id}/link", "POST", {
            "conversationId": conv_id, "targetType": "Lead", "targetId": "nonexistent",
        }, expect_error=True)
        self.assertEqual(code, 403, "identity link requires edit rights on the conversation")

        code, _ = self.sales_api(f"/Fusanhe/conversation/{conv_id}/handoff", "POST", {
            "summary": "should not be allowed", "dateEnd": "2099-01-01",
        }, expect_error=True)
        self.assertEqual(code, 403, "handoff requires access to the conversation (own scope)")

        _, draft = admin_api(f"/Fusanhe/conversation/{conv_id}/generate-draft", "POST", {})
        code, _ = self.sales_api(f"/Fusanhe/draft/{draft['draftId']}/approve", "POST",
                                 {"draftText": "x"}, expect_error=True)
        self.assertEqual(code, 403, "salesperson must not approve outbound")

        code, _ = self.sales_api(f"/AIReplyDraft/{draft['draftId']}", "PATCH",
                                 {"status": "approved"}, expect_error=True)
        self.assertIn(code, (403, 404), "PATCH must not forge approval")
        code, _ = admin_api(f"/ExternalConversation/{conv_id}", "PATCH", {"status": "sent"}, expect_error=True)
        self.assertEqual(code, 403, "conversation send states are pipeline-owned")
        code, _ = admin_api(f"/ExternalConversation/{conv_id}", "PATCH", {"controlMode": "human"}, expect_error=True)
        self.assertEqual(code, 403, "control mode must go through the audited action")
        _, conv_detail = admin_api(f"/ExternalConversation/{conv_id}")
        code, _ = admin_api("/OutboundTask", "POST", {
            "name": "forged", "conversationId": conv_id, "replyDraftId": draft["draftId"],
            "channelId": conv_detail["channelId"], "idempotencyKey": "fake-key-" + self.stamp,
            "status": "pending",
        }, expect_error=True)
        self.assertIn(code, (400, 403),
                      "plain CRUD cannot create tasks: idempotencyKey is read-only+required (400), guard hook backs it up (403)")
        code, _ = admin_api("/ExternalMessage", "POST", {
            "name": "fake-out", "conversationId": conv_id, "direction": "outbound",
            "body": "fake", "sentAt": "2026-01-01 00:00:00",
            "externalId": "fake-ext-" + self.stamp, "contentHash": "fake-hash",
        }, expect_error=True)
        self.assertEqual(code, 403, "outbound messages cannot be fabricated via CRUD")

    # ---- 9. takeover and pause block unsent tasks ----

    def test_09_takeover_blocks_unsent_tasks(self):
        _, conv = self.intake(
            f"CONV-{self.stamp}-G", f"MSG-{self.stamp}-G1",
            email=f"takeover.{self.stamp}@visitor.example", externalUserId=f"uid-to-{self.stamp}",
        )
        conv_id = conv["conversationId"]
        _, draft = admin_api(f"/Fusanhe/conversation/{conv_id}/generate-draft", "POST", {})
        _, approved = admin_api(f"/Fusanhe/draft/{draft['draftId']}/approve", "POST", {})
        task_id = approved["taskId"]

        bootstrap_headers = {"X-Automation-Token": AUTO_TOKEN}
        agent_key = f"phase1-agent-{self.stamp}"
        _, reg = api("/Fusanhe/agent/register", "POST", {
            "agentKey": agent_key, "mode": "mock", "capabilities": ["Website"],
        }, headers=bootstrap_headers)
        self.assertEqual(reg.get("mode"), "mock")
        agent_headers = {"X-Automation-Token": reg["credential"]}

        _, claimed = api("/Fusanhe/agent/claim", "POST", {"agentKey": agent_key}, headers=agent_headers)
        self.assertTrue(claimed.get("paused"), "paused system must refuse to hand out tasks")

        _, control = admin_api(f"/Fusanhe/conversation/{conv_id}/control", "POST", {"mode": "human"})
        self.assertEqual(control["controlMode"], "human")
        self.assertGreaterEqual(control.get("unsentTasksBlocked", 0), 1)

        _, audit = admin_api("/AutomationAudit?" + sp(where=[
            {"type": "equals", "attribute": "eventType", "value": "conversation.control"},
        ]))
        self.assertGreaterEqual(audit["total"], 1, "takeover must be audited")

        _, cancelled = admin_api(f"/Fusanhe/task/{task_id}/cancel", "POST", {})
        self.assertEqual(cancelled["status"], "cancelled")
        code, _ = admin_api(f"/Fusanhe/task/{task_id}/cancel", "POST", {}, expect_error=True)
        self.assertEqual(code, 409, "cancelling twice must conflict")

        _, control = admin_api(f"/Fusanhe/conversation/{conv_id}/control", "POST", {"mode": "aiAssist"})
        self.assertEqual(control["controlMode"], "aiAssist")

    # ---- 10. approved content snapshot is immutable ----

    def test_10_snapshot_immutable_after_approval(self):
        _, conv = self.intake(
            f"CONV-{self.stamp}-H", f"MSG-{self.stamp}-H1",
            email=f"snapshot.{self.stamp}@visitor.example", externalUserId=f"uid-snap-{self.stamp}",
        )
        conv_id = conv["conversationId"]
        _, draft = admin_api(f"/Fusanhe/conversation/{conv_id}/generate-draft", "POST", {})
        _, approved = admin_api(f"/Fusanhe/draft/{draft['draftId']}/approve", "POST",
                                {"draftText": draft["draftText"] + " SNAPSHOT-MARK"})
        code, _ = admin_api(f"/AIReplyDraft/{draft['draftId']}", "PATCH",
                            {"draftText": "tampered"}, expect_error=True)
        self.assertEqual(code, 403, "approved drafts are immutable through record CRUD")
        _, task = admin_api(f"/OutboundTask/{approved['taskId']}")
        self.assertTrue((task.get("contentSnapshot") or "").endswith("SNAPSHOT-MARK"),
                        "the task holds the approved snapshot")

    # ---- 11. knowledge validity / approval / re-review ----

    def test_11_knowledge_gate(self):
        _, conv = self.intake(
            f"CONV-{self.stamp}-K", f"MSG-{self.stamp}-K1",
            email=f"know.{self.stamp}@visitor.example", externalUserId=f"uid-know-{self.stamp}",
        )
        conv_id = conv["conversationId"]
        # Park pre-existing approved docs from earlier runs so they cannot
        # crowd the first-5 knowledge window before this run's docs.
        _, pre = admin_api("/KnowledgeDocument?" + sp(where=[
            {"type": "equals", "attribute": "approvalStatus", "value": "approved"},
        ]))
        for d0 in pre["list"]:
            admin_api(f"/KnowledgeDocument/{d0['id']}", "PATCH", {"approvalStatus": "expired"})
        _, expired = admin_api("/KnowledgeDocument", "POST", {
            "name": f"expired-{self.stamp}", "filePath": f"/tmp/expired-{self.stamp}.txt",
            "approvalStatus": "approved", "effectiveFrom": "2020-01-01", "effectiveTo": "2020-12-31",
            "extractedText": "EXPIRED-KNOWLEDGE-MARK payment terms net 30",
        })
        _, valid = admin_api("/KnowledgeDocument", "POST", {
            "name": f"valid-{self.stamp}", "filePath": f"/tmp/valid-{self.stamp}.txt",
            "approvalStatus": "approved", "effectiveFrom": "2020-01-01", "effectiveTo": "2099-12-31",
            "extractedText": "VALID-KNOWLEDGE-MARK hydraulic fittings catalogue",
        })
        _, draft_doc = admin_api("/KnowledgeDocument", "POST", {
            "name": f"draft-{self.stamp}", "filePath": f"/tmp/draft-{self.stamp}.txt",
            "approvalStatus": "draft",
            "extractedText": "DRAFT-KNOWLEDGE-MARK secret price list",
        })
        _, gen = admin_api(f"/Fusanhe/conversation/{conv_id}/generate-draft", "POST", {})
        cited = gen.get("citedKnowledge") or []
        self.assertIn(valid["id"], cited, "valid approved knowledge is usable")
        self.assertNotIn(expired["id"], cited, "expired knowledge must not enter the AI context")
        self.assertNotIn(draft_doc["id"], cited, "unreviewed knowledge must not enter the AI context")

        # scanner: checksum change sends approved documents back to draft
        doc_path = os.path.normpath(os.path.join(
            os.path.dirname(__file__), "..", "knowledge", "demo", f"phase1-recheck-{self.stamp}.md"))
        try:
            with open(doc_path, "w") as f:
                f.write("RECHECK-KNOWLEDGE-MARK v1")
            admin_api("/Fusanhe/knowledge/scan", "POST", {})
            _, docs = admin_api("/KnowledgeDocument?" + sp(where=[
                {"type": "equals", "attribute": "name", "value": f"phase1-recheck-{self.stamp}.md"},
            ]))
            doc = docs["list"][0]
            admin_api(f"/KnowledgeDocument/{doc['id']}", "PATCH", {"approvalStatus": "approved"})
            with open(doc_path, "w") as f:
                f.write("RECHECK-KNOWLEDGE-MARK v2 changed content")
            admin_api("/Fusanhe/knowledge/scan", "POST", {})
            _, after = admin_api(f"/KnowledgeDocument/{doc['id']}")
            self.assertEqual(after["approvalStatus"], "draft", "changed content must be re-reviewed")
        finally:
            if os.path.exists(doc_path):
                os.remove(doc_path)

    # ---- 12. connector failures do not block CRM ----

    def test_12_channel_failure_does_not_block_crm(self):
        _, status = admin_api("/Fusanhe/status")
        self.assertIn("channels", status)
        _, conv = self.intake(
            f"CONV-{self.stamp}-L", f"MSG-{self.stamp}-L1",
            email=f"crm.{self.stamp}@visitor.example", externalUserId=f"uid-crm-{self.stamp}",
        )
        _, task = admin_api(f"/Fusanhe/conversation/{conv['conversationId']}/handoff", "POST", {
            "summary": f"CRM resilience {self.stamp}", "assignedUserId": self.admin_id,
            "dateEnd": "2099-02-01",
        })
        self.assertTrue(task["taskId"])

    # ---- 13 (phase A). mock loop refuses while paused ----

    def test_13_paused_mock_loop_refuses_claim(self):
        _, conv = self.intake(
            f"CONV-{self.stamp}-M", f"MSG-{self.stamp}-M1",
            email=f"loop.{self.stamp}@visitor.example", externalUserId=f"uid-loop-{self.stamp}",
        )
        conv_id = conv["conversationId"]
        _, draft = admin_api(f"/Fusanhe/conversation/{conv_id}/generate-draft", "POST", {})
        self.assertEqual(draft["provider"], "mock")
        _, approved = admin_api(f"/Fusanhe/draft/{draft['draftId']}/approve", "POST", {})
        self.assertEqual(approved["executionMode"], "mock")
        bootstrap_headers = {"X-Automation-Token": AUTO_TOKEN}
        _, registration = api("/Fusanhe/agent/register", "POST", {
            "agentKey": f"phase1-loop-agent-{self.stamp}", "mode": "mock", "capabilities": ["Website"],
        }, headers=bootstrap_headers)
        agent_headers = {"X-Automation-Token": registration["credential"]}
        _, claimed = api("/Fusanhe/agent/claim", "POST",
                         {"agentKey": f"phase1-loop-agent-{self.stamp}"}, headers=agent_headers)
        self.assertTrue(claimed.get("paused"))

    # ---- 14. explicit errors for empty / conflicting input ----

    def test_14_explicit_error_feedback(self):
        _, conv = self.intake(
            f"CONV-{self.stamp}-N", f"MSG-{self.stamp}-N1",
            email=f"err.{self.stamp}@visitor.example", externalUserId=f"uid-err-{self.stamp}",
        )
        conv_id = conv["conversationId"]
        code, _ = admin_api(f"/Fusanhe/conversation/{conv_id}/handoff", "POST", {"summary": ""}, expect_error=True)
        self.assertEqual(code, 400, "empty summary must be a 400")
        code, _ = admin_api(f"/Fusanhe/conversation/{conv_id}/control", "POST", {"mode": "bogus"}, expect_error=True)
        self.assertEqual(code, 400, "bogus control mode must be a 400")
        code, _ = admin_api("/Fusanhe/identity/nonexistent/candidates?conversationId=nonexistent", expect_error=True)
        self.assertEqual(code, 404)
        code, _ = admin_api("/Fusanhe/mock/intake", "POST",
                            {"conversationExternalId": "", "messageExternalId": "", "body": ""},
                            expect_error=True)
        self.assertEqual(code, 400)

    def test_15_agent_credentials_are_bound_rotatable_and_independently_revocable(self):
        bootstrap = {"X-Automation-Token": AUTO_TOKEN}
        key_a = f"credential-a-{self.stamp}"
        key_b = f"credential-b-{self.stamp}"
        _, reg_a = api("/Fusanhe/agent/register", "POST", {"agentKey": key_a, "mode": "mock"}, headers=bootstrap)
        _, reg_b = api("/Fusanhe/agent/register", "POST", {"agentKey": key_b, "mode": "mock"}, headers=bootstrap)
        auth_a = {"X-Automation-Token": reg_a["credential"]}
        auth_b = {"X-Automation-Token": reg_b["credential"]}

        code, _ = api("/Fusanhe/agent/claim", "POST", {"agentKey": key_b}, headers=auth_a, expect_error=True)
        self.assertEqual(403, code, "credential A must not authenticate as B")
        _, ok_b = api("/Fusanhe/agent/claim", "POST", {"agentKey": key_b}, headers=auth_b)
        self.assertTrue(ok_b.get("paused"))

        _, rotated = admin_api(f"/Fusanhe/agent/{reg_a['agentId']}/credential/rotate", "POST", {})
        code, _ = api("/Fusanhe/agent/claim", "POST", {"agentKey": key_a}, headers=auth_a, expect_error=True)
        self.assertEqual(403, code, "rotation must invalidate the previous credential")
        rotated_auth = {"X-Automation-Token": rotated["credential"]}
        _, ok_a = api("/Fusanhe/agent/claim", "POST", {"agentKey": key_a}, headers=rotated_auth)
        self.assertTrue(ok_a.get("paused"))

        admin_api(f"/Fusanhe/agent/{reg_a['agentId']}/credential/revoke", "POST", {})
        code, _ = api("/Fusanhe/agent/claim", "POST", {"agentKey": key_a}, headers=rotated_auth, expect_error=True)
        self.assertEqual(403, code)
        _, still_ok_b = api("/Fusanhe/agent/claim", "POST", {"agentKey": key_b}, headers=auth_b)
        self.assertTrue(still_ok_b.get("paused"), "revoking A must not affect B")

        _, stored_a = admin_api(f"/AutomationAgent/{reg_a['agentId']}")
        serialized = json.dumps(stored_a)
        self.assertNotIn(reg_a["credential"], serialized)
        self.assertNotIn(rotated["credential"], serialized)

    def test_16_request_id_correlates_response_error_and_audit(self):
        _, conv = self.intake(
            f"CONV-{self.stamp}-RID", f"MSG-{self.stamp}-RID",
            email=f"rid.{self.stamp}@visitor.example",
        )
        request_id = f"phase1-{self.stamp}-request"
        auth = "Basic " + base64.b64encode(f"{ADMIN_USER}:{ADMIN_PASS}".encode()).decode()
        url = BASE + f"/Fusanhe/conversation/{conv['conversationId']}/control"
        req = urllib.request.Request(
            url,
            json.dumps({"mode": "human"}).encode(),
            {"Content-Type": "application/json", "Authorization": auth, "X-Request-Id": request_id},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as response:
            self.assertEqual(request_id, response.headers.get("X-Request-Id"))

        _, audits = admin_api("/AutomationAudit?" + sp(where=[
            {"type": "equals", "attribute": "eventType", "value": "conversation.control"},
        ]))
        self.assertTrue(any((item.get("details") or {}).get("requestId") == request_id for item in audits["list"]))

        bad_id = request_id + "-bad"
        bad = urllib.request.Request(
            url,
            json.dumps({"mode": "invalid"}).encode(),
            {"Content-Type": "application/json", "Authorization": auth, "X-Request-Id": bad_id},
            method="POST",
        )
        with self.assertRaises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(bad, timeout=30)
        payload = json.loads(caught.exception.read())
        self.assertEqual(400, caught.exception.code)
        self.assertEqual(bad_id, caught.exception.headers.get("X-Request-Id"))
        self.assertEqual({"code": "invalid_request", "requestId": bad_id}, payload["error"])


class Phase1SendLoop(unittest.TestCase):
    """Scenario 9/13 phase B: run with FUSANHE_OUTBOUND_PAUSED=false."""

    @classmethod
    def setUpClass(cls):
        cls.stamp = str(int(time.time()))
        _, app = admin_api("/App/user")
        cls.admin_id = app["user"]["id"]

    def intake(self, conv_ext, msg_ext, **extra):
        payload = {
            "channelType": "Website",
            "conversationExternalId": conv_ext,
            "messageExternalId": msg_ext,
            "body": extra.pop("body", "Send loop check."),
        }
        payload.update(extra)
        return admin_api("/Fusanhe/mock/intake", "POST", payload)

    def claim_until(self, agent_key, wanted_task_id, headers, max_rounds=6):
        """Claim may return other pending demo tasks; park them and retry."""
        for _ in range(max_rounds):
            _, claimed = api("/Fusanhe/agent/claim", "POST", {"agentKey": agent_key}, headers=headers)
            self.assertFalse(claimed.get("paused"))
            task = claimed.get("task")
            if task is None:
                continue
            if task["id"] == wanted_task_id:
                return task
            admin_api(f"/Fusanhe/task/{task['id']}/cancel", "POST", {})
        self.fail("wanted task was never handed out")

    def test_send_loop_human_takeover_and_mock_receipt(self):
        _, conv = self.intake(
            f"CONV-LOOP-{self.stamp}", f"MSG-LOOP-{self.stamp}",
            email=f"sendloop.{self.stamp}@visitor.example", externalUserId=f"uid-sendloop-{self.stamp}",
        )
        conv_id = conv["conversationId"]
        _, draft = admin_api(f"/Fusanhe/conversation/{conv_id}/generate-draft", "POST", {})
        _, approved = admin_api(f"/Fusanhe/draft/{draft['draftId']}/approve", "POST", {})
        task_id = approved["taskId"]

        bootstrap_headers = {"X-Automation-Token": AUTO_TOKEN}
        agent_key = f"phase1-send-agent-{self.stamp}"
        _, registration = api("/Fusanhe/agent/register", "POST", {
            "agentKey": agent_key, "mode": "mock", "capabilities": ["Website"],
        }, headers=bootstrap_headers)
        agent_headers = {"X-Automation-Token": registration["credential"]}

        # takeover before claim: the pending automatic task is not handed out
        admin_api(f"/Fusanhe/conversation/{conv_id}/control", "POST", {"mode": "human"})
        _, claimed = api("/Fusanhe/agent/claim", "POST", {"agentKey": agent_key}, headers=agent_headers)
        while claimed.get("task") and claimed["task"]["id"] != task_id:
            admin_api(f"/Fusanhe/task/{claimed['task']['id']}/cancel", "POST", {})
            _, claimed = api("/Fusanhe/agent/claim", "POST", {"agentKey": agent_key}, headers=agent_headers)
        self.assertIsNone(claimed.get("task"), "human takeover must block automatic execution")
        admin_api(f"/Fusanhe/conversation/{conv_id}/control", "POST", {"mode": "aiAssist"})

        # claim after resume, then takeover again: sending must be refused
        task = self.claim_until(agent_key, task_id, agent_headers)
        self.assertEqual(task["body"], draft["draftText"] or task["body"])
        admin_api(f"/Fusanhe/conversation/{conv_id}/control", "POST", {"mode": "human"})
        code, _ = api(f"/Fusanhe/agent/task/{task_id}/sending", "POST", {"agentKey": agent_key},
                      headers=agent_headers, expect_error=True)
        self.assertEqual(code, 409, "takeover after claim must block sending")
        admin_api(f"/Fusanhe/conversation/{conv_id}/control", "POST", {"mode": "aiAssist"})

        # send + result with mock receipt
        _, sending = api(f"/Fusanhe/agent/task/{task_id}/sending", "POST",
                         {"agentKey": agent_key}, headers=agent_headers)
        self.assertTrue(sending["ok"])
        _, result = api(f"/Fusanhe/agent/task/{task_id}/result", "POST", {
            "agentKey": agent_key, "success": True, "platformMessageId": f"MOCK-{task_id}",
        }, headers=agent_headers)
        self.assertEqual(result["status"], "sent")
        # duplicate result is idempotent
        _, again = api(f"/Fusanhe/agent/task/{task_id}/result", "POST", {
            "agentKey": agent_key, "success": True, "platformMessageId": f"MOCK-{task_id}",
        }, headers=agent_headers)
        self.assertTrue(again.get("idempotent"))

        _, conv_after = admin_api(f"/ExternalConversation/{conv_id}")
        self.assertEqual(conv_after["status"], "replied", "conversation records a reply, not a send state")
        _, messages = admin_api("/ExternalMessage?" + sp(where=[
            {"type": "equals", "attribute": "conversationId", "value": conv_id},
            {"type": "equals", "attribute": "direction", "value": "outbound"},
        ]))
        self.assertEqual(messages["total"], 1)
        self.assertEqual(messages["list"][0]["deliveryStatus"], "mockSent",
                         "mock receipts must be visibly simulated")


if __name__ == "__main__":
    unittest.main()
