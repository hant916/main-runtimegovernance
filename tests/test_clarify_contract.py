import json
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from ailuros.adapters.clarify_contract import ClarifyGovernanceRequest
from ailuros.models import GovernanceDecision, GovernanceDecisionType, Severity

ANALYZE_DOCUMENT_REQUEST = {
    "app": "clarify",
    "action": "analyze_document",
    "content_type": "web_page",
    "risk_surface": "browsing",
    "tool_requested": "read_page",
    "context": {"url": "https://example.com/docs/policy"},
    "evidence_ids": ["evt_001", "evt_002"],
}


def test_request_serializes_to_json() -> None:
    req = ClarifyGovernanceRequest(**ANALYZE_DOCUMENT_REQUEST)
    dumped = req.model_dump(mode="json")
    assert dumped["app"] == "clarify"
    assert dumped["action"] == "analyze_document"
    assert dumped["content_type"] == "web_page"
    assert dumped["risk_surface"] == "browsing"
    assert dumped["tool_requested"] == "read_page"
    assert dumped["context"] == {"url": "https://example.com/docs/policy"}
    assert dumped["evidence_ids"] == ["evt_001", "evt_002"]

    raw = req.model_dump_json()
    restored = ClarifyGovernanceRequest.model_validate_json(raw)
    assert restored == req


def test_request_requires_all_required_fields() -> None:
    with pytest.raises(ValidationError):
        ClarifyGovernanceRequest()

    with pytest.raises(ValidationError):
        ClarifyGovernanceRequest(app="clarify")

    with pytest.raises(ValidationError):
        ClarifyGovernanceRequest(app="clarify", action="analyze_document")


def test_request_optional_fields_default() -> None:
    req = ClarifyGovernanceRequest(
        app="clarify",
        action="check_navigation",
        content_type="user_action",
        risk_surface="browsing",
        tool_requested="navigate",
    )
    assert req.context == {}
    assert req.evidence_ids == []


def test_request_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        ClarifyGovernanceRequest(
            app="clarify",
            action="analyze_document",
            content_type="web_page",
            risk_surface="browsing",
            tool_requested="read_page",
            unknown_field="should_fail",
        )


def test_governance_decision_has_contract_fields() -> None:
    decision = GovernanceDecision(
        decision_id="dec_001",
        run_id="run_001",
        decision=GovernanceDecisionType.ALLOW,
        allowed=True,
        reason="No policy violations.",
        severity=Severity.LOW,
        matched_policy_ids=["pol_default_allow"],
        risk_level=Severity.LOW,
        evidence_refs=["evt_001"],
        created_at=datetime.now(UTC),
    )
    dumped = decision.model_dump(mode="json")
    assert dumped["decision"] == "allow"
    assert dumped["risk_level"] == "low"
    assert dumped["matched_policy_ids"] == ["pol_default_allow"]
    assert dumped["reason"] == "No policy violations."
    assert dumped["evidence_refs"] == ["evt_001"]


def test_contract_examples_serialize_to_json() -> None:
    req = ClarifyGovernanceRequest(**ANALYZE_DOCUMENT_REQUEST)
    json_str = req.model_dump_json()
    parsed = json.loads(json_str)
    assert parsed["app"] == "clarify"
    assert parsed["action"] == "analyze_document"
    assert "context" in parsed
    assert "evidence_ids" in parsed
