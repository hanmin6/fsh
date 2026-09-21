#!/usr/bin/env python3
import json
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


class AgentCredentialsContract(unittest.TestCase):
    def test_lifecycle_fields_exist_and_hash_is_not_api_writable(self):
        data = json.loads((ROOT / "custom/Espo/Custom/Resources/metadata/entityDefs/AutomationAgent.json").read_text())
        fields = data["fields"]
        for name in ("credentialHash", "credentialVersion", "credentialIssuedAt", "credentialExpiresAt", "credentialRevokedAt", "credentialLastUsedAt"):
            self.assertIn(name, fields)
            self.assertTrue(fields[name]["readOnly"])

    def test_plaintext_is_issued_once_and_only_hash_is_stored(self):
        source = (ROOT / "custom/Espo/Custom/Tools/Fusanhe/AutomationAuth.php").read_text()
        self.assertIn("password_hash", source)
        self.assertIn("password_verify", source)
        self.assertIn("random_bytes(48)", source)
        self.assertNotIn("'credential' => $plain,\n            'credentialHash'", source)

    def test_binding_revocation_expiry_rotation_and_legacy_cutoff(self):
        source = (ROOT / "custom/Espo/Custom/Tools/Fusanhe/AutomationAuth.php").read_text()
        for text in ("agentKey", "credentialRevokedAt", "credentialExpiresAt", "credentialVersion", "FUSANHE_AUTOMATION_LEGACY_UNTIL"):
            self.assertIn(text, source)

    def test_non_registration_actions_authenticate_declared_agent(self):
        api = ROOT / "custom/Espo/Custom/Tools/Fusanhe/Api"
        for name in ("PostAgentHeartbeat.php", "PostAgentClaim.php", "PostTaskSending.php", "PostTaskResult.php"):
            source = (api / name).read_text()
            self.assertIn("assertAgent", source)
            self.assertIn("agentKey", source)
        self.assertIn("assertBootstrap", (api / "PostAgentRegister.php").read_text())

    def test_auth_failure_is_deliberately_nonspecific(self):
        source = (ROOT / "custom/Espo/Custom/Tools/Fusanhe/AutomationAuth.php").read_text()
        self.assertNotIn("Agent not registered", source)
        forbidden_lines = [line for line in source.splitlines() if "throw new Forbidden" in line]
        self.assertTrue(forbidden_lines)
        self.assertTrue(all("Automation authentication failed" in line for line in forbidden_lines))

    def test_admin_rotation_and_revocation_are_acl_guarded_and_audited(self):
        routes = json.loads((ROOT / "custom/Espo/Custom/Resources/routes.json").read_text())
        by_route = {item["route"]: item for item in routes}
        for action in ("rotate", "revoke"):
            route = f"/Fusanhe/agent/:id/credential/{action}"
            self.assertIn(route, by_route)
            self.assertNotIn("noAuth", by_route[route])
            class_name = by_route[route]["actionClassName"].split("\\")[-1]
            source = (ROOT / f"custom/Espo/Custom/Tools/Fusanhe/Api/{class_name}.php").read_text()
            self.assertIn("requireEntityScope", source)
            self.assertIn("$this->kernel->audit", source)


if __name__ == "__main__":
    unittest.main()
