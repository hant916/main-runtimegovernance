from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from ailuros import GovernanceDecision, GovernanceDecisionType, Severity


def _decision(decision_type: GovernanceDecisionType, **kwargs) -> GovernanceDecision:
    base = dict(
        decision_id="dec_contract_test",
        run_id="run_contract_test",
        decision=decision_type,
        allowed=decision_type in {GovernanceDecisionType.ALLOW, GovernanceDecisionType.WARN},
        reason="Contract test reason.",
        created_at=datetime.now(tz=UTC),
    )
    base.update(kwargs)
    return GovernanceDecision(**base)


ALLOW_EXECUTABLE = {GovernanceDecisionType.ALLOW, GovernanceDecisionType.WARN}
BLOCK_EXECUTABLE = {
    GovernanceDecisionType.BLOCK,
    GovernanceDecisionType.SANITIZE,
    GovernanceDecisionType.REQUIRE_REVIEW,
}


class TestExecutableSuccess:
    @pytest.mark.parametrize("decision_type", list(ALLOW_EXECUTABLE))
    def test_allow_is_executable_success(self, decision_type: GovernanceDecisionType) -> None:
        decision = _decision(decision_type)
        assert decision.allowed is True

    @pytest.mark.parametrize("decision_type", list(BLOCK_EXECUTABLE))
    def test_block_or_review_is_not_executable_success(
        self, decision_type: GovernanceDecisionType,
    ) -> None:
        decision = _decision(decision_type)
        assert decision.allowed is False

    @pytest.mark.parametrize(
        "decision_type, expected_allowed",
        [
            (GovernanceDecisionType.ALLOW, True),
            (GovernanceDecisionType.WARN, True),
            (GovernanceDecisionType.SANITIZE, False),
            (GovernanceDecisionType.REQUIRE_REVIEW, False),
            (GovernanceDecisionType.BLOCK, False),
        ],
    )
    def test_allowed_field_consistent_with_decision_type(
        self, decision_type: GovernanceDecisionType, expected_allowed: bool,
    ) -> None:
        decision = _decision(decision_type)
        assert decision.allowed is expected_allowed
        assert decision.decision is decision_type


class TestDecisionShape:
    def test_rejects_extra_fields(self) -> None:
        with pytest.raises(ValidationError):
            GovernanceDecision(
                decision_id="bad",
                run_id="bad",
                decision=GovernanceDecisionType.ALLOW,
                allowed=True,
                reason="test",
                created_at=datetime.now(tz=UTC),
                unknown_field="should_fail",
            )

    def test_requires_timezone_aware_created_at(self) -> None:
        with pytest.raises(ValidationError):
            GovernanceDecision(
                decision_id="bad",
                run_id="bad",
                decision=GovernanceDecisionType.ALLOW,
                allowed=True,
                reason="test",
                created_at=datetime.now(),  # no tz
            )

    def test_rejects_invalid_decision_enum(self) -> None:
        with pytest.raises(ValidationError):
            GovernanceDecision(
                decision_id="bad",
                run_id="bad",
                decision="invalid_state",
                allowed=True,
                reason="test",
                created_at=datetime.now(tz=UTC),
            )


class TestReasonAndEvidence:
    def test_reason_field_is_explicit(self) -> None:
        decision = _decision(
            GovernanceDecisionType.ALLOW,
            reason="Explicit reason for contract test.",
        )
        assert decision.reason == "Explicit reason for contract test."

    def test_evidence_refs_are_explicit(self) -> None:
        decision = _decision(
            GovernanceDecisionType.BLOCK,
            evidence_refs=["evt_block_001", "policy_match_002"],
        )
        assert decision.evidence_refs == ["evt_block_001", "policy_match_002"]

    def test_evidence_refs_default_to_empty(self) -> None:
        decision = _decision(GovernanceDecisionType.ALLOW)
        assert decision.evidence_refs == []

    def test_matched_policy_ids_are_explicit(self) -> None:
        decision = _decision(
            GovernanceDecisionType.REQUIRE_REVIEW,
            matched_policy_ids=["pol_high_value_tx", "pol_aml_check"],
        )
        assert decision.matched_policy_ids == ["pol_high_value_tx", "pol_aml_check"]


class TestSerialization:
    def test_round_trips_through_json(self) -> None:
        decision = _decision(
            GovernanceDecisionType.BLOCK,
            reason="Blocked by policy.",
            evidence_refs=["ref_001"],
            matched_policy_ids=["pol_block_test"],
            risk_level=Severity.HIGH,
            input_hash="abc123",
            tool_name="test.tool",
        )
        raw = decision.model_dump_json()
        restored = GovernanceDecision.model_validate_json(raw)
        assert restored == decision

    def test_decision_type_string_values(self) -> None:
        assert GovernanceDecisionType.ALLOW.value == "allow"
        assert GovernanceDecisionType.BLOCK.value == "block"
        assert GovernanceDecisionType.REQUIRE_REVIEW.value == "require_review"
        assert GovernanceDecisionType.WARN.value == "warn"
        assert GovernanceDecisionType.SANITIZE.value == "sanitize"
