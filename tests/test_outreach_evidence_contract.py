import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CUSTOM = ROOT / "custom" / "Espo" / "Custom"


def read(path: str) -> str:
    return (CUSTOM / path).read_text(encoding="utf-8")


def test_metadata_and_routes_are_bounded_and_private():
    evidence = json.loads(read("Resources/metadata/entityDefs/OutreachEvidence.json"))
    research = json.loads(read("Resources/metadata/entityDefs/ProspectResearch.json"))
    routes = json.loads(read("Resources/routes.json"))
    fields = evidence["fields"]
    assert fields["screenshotFileKey"]["maxLength"] == 48
    assert fields["screenshotSha256"]["maxLength"] == 64
    assert fields["researchStatus"]["options"] == ["pending", "running", "completed", "failed"]
    assert research["fields"]["sources"]["type"] == "jsonObject"
    route_methods = {(r["route"], r["method"]) for r in routes}
    assert ("/Fusanhe/outreach/evidence", "post") in route_methods
    assert ("/Fusanhe/outreach/evidence", "get") in route_methods
    assert ("/Fusanhe/outreach/evidence/:id/screenshot", "get") in route_methods
    assert ("/Fusanhe/outreach/evidence/:id/research", "post") in route_methods


def test_policy_rejects_unbounded_images_and_redacts_private_contact_data():
    policy = read("Tools/Fusanhe/OutreachEvidencePolicy.php")
    assert "MAX_IMAGE_BYTES = 4 * 1024 * 1024" in policy
    assert "image/(?:png|jpeg|webp)" in policy
    assert "[email]" in policy and "[phone]" in policy
    assert "customerSnapshot" in policy


def test_service_is_crm_only_and_idempotent():
    service = read("Tools/Fusanhe/OutreachEvidenceService.php")
    assert "idempotencyKey" in service
    assert "requestHash" in service
    assert "External message ID already contains different evidence" in service
    assert "outreach.evidence.recorded" in service
    assert "OutboundTask" not in service
    assert "send_message" not in service
    assert "Muse" not in service
    assert "researchStatus' => 'completed'" in service
    assert "messageContext' => $safe['messageContext']" in service
    assert "function list(string $targetType" in service
    assert "researchAttempts' < 3" in service or "researchAttempts<' => 3" in service
    assert "OutboundTask" not in service


def test_research_retry_is_scheduled_and_sources_are_provenanced():
    jobs = json.loads((ROOT / "custom/Espo/Custom/Resources/metadata/app/scheduledJobs.json").read_text())
    assert jobs["FusanheOutreachResearch"]["jobClassName"].endswith("OutreachResearch")
    job = (ROOT / "custom/Espo/Custom/Classes/Jobs/OutreachResearch.php").read_text()
    assert "service->tick()" in job and "never sends" in job
    gateway = read("Tools/Fusanhe/TextGateway.php")
    assert "web_search_call" in gateway and "verifiedSources" in gateway
    service = read("Tools/Fusanhe/OutreachEvidenceService.php")
    assert "nextAt' => $attempts < 3 ? $next : null" in service


def test_api_actions_are_acl_scoped():
    for path, scope, action in [
        ("Api/PostOutreachEvidence.php", "OutreachEvidence", "create"),
        ("Api/GetOutreachEvidenceList.php", "OutreachEvidence", "read"),
        ("Api/GetOutreachEvidence.php", "OutreachEvidence", "read"),
        ("Api/GetOutreachScreenshot.php", "OutreachEvidence", "read"),
        ("Api/PostOutreachResearch.php", "OutreachEvidence", "edit"),
    ]:
        content = read("Tools/Fusanhe/" + path)
        assert f"requireScope('{scope}', '{action}')" in content
        assert "requireEntityScope('OutreachEvidence'" in content or "requireEntityScope($targetType" in content or action == "create"
