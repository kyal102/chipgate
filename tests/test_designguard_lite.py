from jarvi3_designguard_lite import LIMITATION, PublicDesignGuardAdapter, run_lite_demo


def test_lite_demo_exposes_public_safe_schema() -> None:
    demo = run_lite_demo()

    assert demo["sample_request"]["schema_version"] == "jarvi3.designguard.v0"
    assert demo["sample_response"]["schema_version"] == "jarvi3.designguard.response.v0"
    assert "DESIGNGUARD_EXPORT_NEEDS_REVIEW" in demo["supported_statuses"]
    assert "private JARVI3" not in demo["sample_response"]["user_message"]


def test_limitations_do_not_claim_silicon_proof() -> None:
    lower = LIMITATION.lower()

    assert "does not prove silicon correctness" in lower
    assert "regulatory compliance" in lower


def test_public_adapter_is_interface_only() -> None:
    adapter = PublicDesignGuardAdapter()

    try:
        adapter.check({})
    except NotImplementedError as exc:
        assert "private ChipGate system" in str(exc)
    else:
        raise AssertionError("PublicDesignGuardAdapter.check should be interface-only")
