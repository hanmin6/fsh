#!/usr/bin/env python3
"""Phase 1 offline contract tests: metadata, services and guards.

These tests verify structure without a running EspoCRM. Behavioral
verification lives in tests/test_phase1_runtime.py (isolated environment).
"""
import json
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
RES = ROOT / "custom/Espo/Custom/Resources"
SRV = ROOT / "custom/Espo/Custom/Tools/Fusanhe"
HOOKS = ROOT / "custom/Espo/Custom/Hooks"


def entity(name):
    return json.loads((RES / f"metadata/entityDefs/{name}.json").read_text())


def read(path):
    return (ROOT / path).read_text()


class ExternalIdentityContract(unittest.TestCase):
    def test_identity_key_is_unique(self):
        d = entity("ExternalIdentity")
        self.assertTrue(d["indexes"]["identityKey"]["unique"])

    def test_identity_links_all_customer_types(self):
        links = entity("ExternalIdentity")["links"]
        for link in ("account", "contact", "lead"):
            self.assertIn(link, links)

    def test_scope_is_acl_protected(self):
        scope = json.loads((RES / "metadata/scopes/ExternalIdentity.json").read_text())
        self.assertTrue(scope["acl"])


class ConversationStateContract(unittest.TestCase):
    def test_status_appends_replied_and_keeps_legacy_values(self):
        options = entity("ExternalConversation")["fields"]["status"]["options"]
        for legacy in ("new", "pending", "waitingApproval", "readyToSend", "sending", "sent", "failed", "closed"):
            self.assertIn(legacy, options, "legacy values must stay for old data")
        self.assertIn("replied", options)

    def test_control_mode_is_independent_field(self):
        d = entity("ExternalConversation")
        self.assertEqual(d["fields"]["controlMode"]["options"], ["aiAssist", "human"])
        self.assertEqual(d["fields"]["controlMode"]["default"], "aiAssist")

    def test_identity_link_exists(self):
        self.assertEqual(entity("ExternalConversation")["links"]["identity"]["entity"], "ExternalIdentity")


class IsolationAndSnapshotContract(unittest.TestCase):
    def test_task_has_execution_mode_and_snapshot(self):
        d = entity("OutboundTask")
        self.assertEqual(d["fields"]["executionMode"]["options"], ["mock", "real"])
        self.assertIn("contentSnapshot", d["fields"])

    def test_agent_has_mock_mode(self):
        self.assertEqual(entity("AutomationAgent")["fields"]["mode"]["options"], ["mock", "real"])

    def test_message_delivery_marks_mock_receipts(self):
        options = entity("ExternalMessage")["fields"]["deliveryStatus"]["options"]
        self.assertIn("mockSent", options)
        self.assertIn("sent", options, "real receipts keep their own status")

    def test_task_parent_accepts_conversation_and_handoff_key_unique(self):
        d = entity("Task")
        self.assertIn("ExternalConversation", d["fields"]["parent"]["entityList"])
        self.assertTrue(d["indexes"]["fusanheHandoffKey"]["unique"])


class ServiceContract(unittest.TestCase):
    def test_no_lead_is_created_on_intake(self):
        source = read("custom/Espo/Custom/Tools/Fusanhe/WorkflowService.php")
        self.assertNotIn("matchOrCreateCustomer", source, "auto customer creation must be gone")
        self.assertIn("'createdLead' => false", source)
        self.assertIn("resolveIdentity", source)

    def test_knowledge_filter_checks_validity_and_acl(self):
        source = read("custom/Espo/Custom/Tools/Fusanhe/WorkflowService.php")
        self.assertIn("effectiveFrom", source)
        self.assertIn("effectiveTo", source)
        self.assertIn("checkEntityRead", source)
        self.assertIn("approvalStatus' => 'approved'", source)

    def test_send_checks_are_consistent(self):
        control = read("custom/Espo/Custom/Tools/Fusanhe/ControlService.php")
        self.assertIn("assertSendAllowed", control)
        self.assertIn("FUSANHE_OUTBOUND_PAUSED", control)
        workflow = read("custom/Espo/Custom/Tools/Fusanhe/WorkflowService.php")
        self.assertEqual(workflow.count("assertSendAllowed"), 2, "markSending and reportResult both gate sends")

    def test_approved_content_is_snapshotted(self):
        workflow = read("custom/Espo/Custom/Tools/Fusanhe/WorkflowService.php")
        self.assertIn("contentSnapshot", workflow)
        self.assertIn("taskBody", workflow, "claim payload reads the snapshot, not the live draft")

    def test_handoff_is_idempotent_and_native(self):
        handoff = read("custom/Espo/Custom/Tools/Fusanhe/HandoffService.php")
        self.assertIn("fusanheHandoffKey", handoff)
        self.assertIn("deduplicated", handoff)
        self.assertIn("'parentType' => 'ExternalConversation'", handoff)

    def test_audit_records_real_actors(self):
        workflow = read("custom/Espo/Custom/Tools/Fusanhe/WorkflowService.php")
        self.assertNotIn("'user','current'", workflow.replace(" ", ""))
        self.assertIn("$user->getId()", workflow)


class GuardContract(unittest.TestCase):
    def test_state_machine_hooks_exist_for_guarded_entities(self):
        for entity_type in ("AIReplyDraft", "OutboundTask", "ExternalConversation", "ExternalMessage"):
            path = HOOKS / entity_type
            self.assertTrue(path.is_dir(), f"missing guard hook for {entity_type}")
            php = next(path.glob("*.php"))
            source = php.read_text()
            self.assertIn("BeforeSave", source)
            self.assertIn("fusanheService", source, "service writes must bypass the guard")

    def test_outbound_task_create_is_service_only(self):
        source = read("custom/Espo/Custom/Hooks/OutboundTask/StateMachineGuard.php")
        self.assertIn("isNew()", source)
        self.assertIn("Forbidden", source)


class RoutesContract(unittest.TestCase):
    def test_phase1_routes_have_action_classes(self):
        routes = json.loads((RES / "routes.json").read_text())
        expected = [
            "/Fusanhe/conversation/:id/manual-draft",
            "/Fusanhe/conversation/:id/control",
            "/Fusanhe/conversation/:id/handoff",
            "/Fusanhe/conversation/:id/handoff-tasks",
            "/Fusanhe/task/:id/cancel",
            "/Fusanhe/identity/:id/candidates",
            "/Fusanhe/identity/:id/link",
            "/Fusanhe/identity/:id/create-customer",
        ]
        by_route = {r["route"]: r for r in routes}
        for route in expected:
            self.assertIn(route, by_route)
            cls = by_route[route]["actionClassName"].split("\\")[-1]
            self.assertTrue((SRV / f"Api/{cls}.php").exists(), f"missing action class {cls}")

    def test_actions_enforce_acl(self):
        for name in ("PostMockIntake", "PostGenerateDraft", "PostKnowledgeScan", "GetDashboard", "GetStatus"):
            source = read(f"custom/Espo/Custom/Tools/Fusanhe/Api/{name}.php")
            self.assertIn("checkScope", source, f"{name} must enforce scope ACL")


class RolesContract(unittest.TestCase):
    def test_bootstrap_grants_task_and_identity_access(self):
        source = read("scripts/bootstrap.py")
        self.assertIn("'Task'", source, "handoff needs Task grants; unlisted scopes mean no access")
        self.assertIn("'ExternalIdentity'", source)


if __name__ == "__main__":
    unittest.main()
