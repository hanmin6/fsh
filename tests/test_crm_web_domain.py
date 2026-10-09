import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class CrmWebDomainContract(unittest.TestCase):
    def test_env_defaults_use_crm_origin_and_safe_runtime_flags(self):
        env = (ROOT / ".env.example").read_text()
        self.assertIn("CRM_DOMAIN=gzfusanhesp.com", env)
        self.assertIn("CRM_PUBLIC_ORIGIN=https://gzfusanhesp.com", env)
        self.assertIn("ESPOCRM_SITE_URL=https://gzfusanhesp.com", env)
        self.assertIn("ESPOCRM_WEBSOCKET_URL=wss://gzfusanhesp.com/ws", env)
        self.assertIn("FUSANHE_PUBLIC_WORKSPACE_ENABLED=false", env)
        self.assertIn("FUSANHE_OUTBOUND_PAUSED=true", env)

    def test_compose_has_loopback_backends_and_edge_profile(self):
        compose = (ROOT / "compose.yaml").read_text()
        self.assertIn('profiles: ["edge"]', compose)
        self.assertIn('"${ESPOCRM_BIND_ADDRESS:-127.0.0.1}:${ESPOCRM_PORT:-8080}:80"', compose)
        self.assertIn('"${ESPOCRM_WEBSOCKET_BIND_ADDRESS:-127.0.0.1}:${ESPOCRM_WEBSOCKET_PORT:-8081}:8080"', compose)
        self.assertIn('"${CADDY_HTTP_PORT:-80}:80"', compose)
        self.assertIn('"${CADDY_HTTPS_PORT:-443}:443"', compose)
        self.assertIn("caddy-data:", compose)
        self.assertIn("caddy-config:", compose)
        self.assertIn("FUSANHE_PUBLIC_WORKSPACE_ENABLED: ${FUSANHE_PUBLIC_WORKSPACE_ENABLED:-false}", compose)
        self.assertNotIn("3306:", compose)

    def test_caddy_routes_crm_and_websocket(self):
        caddy = (ROOT / "deploy/caddy/Caddyfile").read_text()
        self.assertIn("{$CRM_DOMAIN}", caddy)
        self.assertIn("path /ws*", caddy)
        self.assertIn("reverse_proxy @crmWebSocket websocket:8080", caddy)
        self.assertIn("reverse_proxy espocrm:80", caddy)

    def test_native_login_and_public_workspace_gate(self):
        login = (ROOT / "client/custom/src/views/fusanhe/login.js").read_text()
        self.assertNotIn("public-workspace", login)
        self.assertNotIn("enterWorkspace", login)
        workspace = (ROOT / "custom/Espo/Custom/Authentication/Workspace.php").read_text()
        self.assertIn("FUSANHE_PUBLIC_WORKSPACE_ENABLED", workspace)
        self.assertIn("FILTER_VALIDATE_BOOLEAN", workspace)
        self.assertIn("FailReason::DENIED", workspace)

    def test_android_is_not_active_ci_and_runbook_keeps_sites_separate(self):
        workflow = (ROOT / ".github/workflows/verify.yml").read_text()
        self.assertNotIn("\n  android:\n", workflow)
        runbook = (ROOT / "docs/CRM_WEB_DEPLOYMENT.md").read_text()
        self.assertIn("gzfusanhesp.com", runbook)
        self.assertIn("fshfoodingredients.com", runbook)
        self.assertIn("不要开放 `8080`、`8081`、`3306`", runbook)


if __name__ == "__main__":
    unittest.main()
