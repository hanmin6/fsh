#!/usr/bin/env python3
import json
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
RES = ROOT / "custom/Espo/Custom/Resources"
TOOLS = ROOT / "custom/Espo/Custom/Tools/Fusanhe"
API = TOOLS / "Api"


class MuseCrmContract(unittest.TestCase):
    def test_lead_has_provenance_and_contact_policy(self):
        data = json.loads((RES / "metadata/entityDefs/Lead.json").read_text())
        fields = data["fields"]
        for field in (
            "fusanheSourceSystem", "fusanheSourceId", "fusanheSourceUrl",
            "fusanheCampaignKey", "fusanheContactPolicy", "fusanheDoNotContact",
            "fusanheLastContactAt", "fusanheLastAgentKey",
        ):
            self.assertIn(field, fields)
        self.assertTrue(data["indexes"]["fusanheSource"]["unique"])
        self.assertEqual(fields["fusanheContactPolicy"]["options"], ["unknown", "allowed", "optedOut", "restricted"])

    def test_routes_are_agent_authenticated(self):
        routes = json.loads((RES / "routes.json").read_text())
        selected = {row["route"]: row for row in routes if row["route"].startswith("/Fusanhe/muse/")}
        self.assertEqual(set(selected), {
            "/Fusanhe/muse/prospects",
            "/Fusanhe/muse/prospect",
            "/Fusanhe/muse/activity",
        })
        self.assertTrue(all(row.get("noAuth") is True for row in selected.values()))
        for row in selected.values():
            name = row["actionClassName"].split("\\")[-1]
            source = (API / f"{name}.php").read_text()
            self.assertIn("assertAgent", source)
            self.assertIn("MuseCrmService", source)

    def test_service_is_narrow_and_policy_guarded(self):
        source = (TOOLS / "MuseCrmService.php").read_text()
        for text in (
            "MuseCRM", "upsertProspect", "recordActivity", "searchProspects",
            "fusanheSourceId", "fusanheDoNotContact", "ExternalIdentity",
            "ExternalConversation", "ExternalMessage", "Conflict",
            "Prospect is marked do-not-contact", "ServiceKernel",
        ):
            self.assertIn(text, source)
        self.assertNotIn("OutboundTask", source, "CRM MCP boundary must not create send tasks")
        self.assertNotIn("Connector", source, "CRM MCP boundary must not send externally")

    def test_docs_define_mcp_tool_mapping_and_no_send_claim(self):
        doc = (ROOT / "docs/MUSE_CODE_CRM_MCP.md").read_text()
        for tool in ("crm_search_prospects", "crm_upsert_prospect", "crm_record_activity"):
            self.assertIn(tool, doc)
        self.assertIn("queued", doc)
        self.assertIn("接口不会发信", doc)


if __name__ == "__main__":
    unittest.main()
