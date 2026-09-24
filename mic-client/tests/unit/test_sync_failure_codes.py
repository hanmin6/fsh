from mic_gateway.adapters.made_in_china.adapter import SiteContractError
from mic_gateway.sync.engine import safe_failure_code


def test_known_site_contract_failure_has_actionable_safe_code() -> None:
    error = SiteContractError(
        "trademessenger_history_incomplete: load control readiness unverified"
    )
    assert safe_failure_code(error) == (
        "trademessenger_history_incomplete_load_control_readiness_unverified"
    )


def test_unknown_failure_never_persists_its_message() -> None:
    error = SiteContractError("buyer@example.com token=not-for-checkpoints")
    assert safe_failure_code(error) == "sitecontracterror"
    assert safe_failure_code(ValueError("buyer@example.com")) == "valueerror"
