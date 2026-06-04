from datetime import UTC, datetime

from ailuros.models import GovernanceDecision, GovernanceDecisionType, Severity
from ailuros.policy.diff import diff_decisions


def _make_decision(
    decision_id: str = "dec_old",
    run_id: str = "run-1",
    decision: GovernanceDecisionType = GovernanceDecisionType.ALLOW,
    allowed: bool = True,
    reason: str = "No matching policy.",
    severity: Severity = Severity.LOW,
    matched_policy_ids: list[str] | None = None,
    tool_name: str | None = None,
) -> GovernanceDecision:
    return GovernanceDecision(
        decision_id=decision_id,
        run_id=run_id,
        decision=decision,
        allowed=allowed,
        reason=reason,
        severity=severity,
        matched_policy_ids=matched_policy_ids or [],
        created_at=datetime.now(UTC),
        tool_name=tool_name,
    )


class TestDiffDecisionsUnchanged:

    def test_identical_decisions_produce_no_changes(self):
        old = _make_decision()
        new = _make_decision(decision_id="dec_new")

        result = diff_decisions(old, new)

        assert result.old_decision_id == "dec_old"
        assert result.new_decision_id == "dec_new"
        assert not result.has_changes
        assert result.change_summary == "No changes detected."
        assert all(d.kind == "unchanged" for d in result.diffs)
        assert len(result.diffs) == 5

    def test_matched_policy_ids_order_is_normalized(self):
        old = _make_decision(
            decision_id="dec_old",
            matched_policy_ids=["policy-b", "policy-a"],
        )
        new = _make_decision(
            decision_id="dec_new",
            matched_policy_ids=["policy-a", "policy-b"],
        )

        result = diff_decisions(old, new)

        pid_diff = [d for d in result.diffs if d.field == "matched_policy_ids"][0]
        assert pid_diff.kind == "unchanged"


class TestDiffDecisionField:

    def test_decision_unchanged(self):
        old = _make_decision(
            decision_id="dec_old",
            decision=GovernanceDecisionType.WARN,
            allowed=True,
        )
        new = _make_decision(
            decision_id="dec_new",
            decision=GovernanceDecisionType.WARN,
            allowed=True,
        )

        result = diff_decisions(old, new)
        d = [d for d in result.diffs if d.field == "decision"][0]

        assert d.kind == "unchanged"
        assert d.old_value == "warn"
        assert d.new_value == "warn"

    def test_allow_to_warn_is_upgrade(self):
        old = _make_decision(
            decision_id="dec_old",
            decision=GovernanceDecisionType.ALLOW,
            allowed=True,
        )
        new = _make_decision(
            decision_id="dec_new",
            decision=GovernanceDecisionType.WARN,
            allowed=True,
        )

        result = diff_decisions(old, new)
        d = [d for d in result.diffs if d.field == "decision"][0]

        assert d.kind == "upgrade"
        assert d.old_value == "allow"
        assert d.new_value == "warn"
        assert "allow -> warn" in d.message

    def test_warn_to_block_is_upgrade(self):
        old = _make_decision(
            decision_id="dec_old",
            decision=GovernanceDecisionType.WARN,
            allowed=True,
        )
        new = _make_decision(
            decision_id="dec_new",
            decision=GovernanceDecisionType.BLOCK,
            allowed=False,
        )

        result = diff_decisions(old, new)
        d = [d for d in result.diffs if d.field == "decision"][0]

        assert d.kind == "upgrade"
        assert d.old_value == "warn"
        assert d.new_value == "block"

    def test_block_to_allow_is_downgrade(self):
        old = _make_decision(
            decision_id="dec_old",
            decision=GovernanceDecisionType.BLOCK,
            allowed=False,
        )
        new = _make_decision(
            decision_id="dec_new",
            decision=GovernanceDecisionType.ALLOW,
            allowed=True,
        )

        result = diff_decisions(old, new)
        d = [d for d in result.diffs if d.field == "decision"][0]

        assert d.kind == "downgrade"
        assert d.old_value == "block"
        assert d.new_value == "allow"

    def test_allow_to_block_is_upgrade(self):
        old = _make_decision(
            decision_id="dec_old",
            decision=GovernanceDecisionType.ALLOW,
            allowed=True,
        )
        new = _make_decision(
            decision_id="dec_new",
            decision=GovernanceDecisionType.BLOCK,
            allowed=False,
        )

        result = diff_decisions(old, new)
        d = [d for d in result.diffs if d.field == "decision"][0]

        assert d.kind == "upgrade"


class TestDiffSeverityField:

    def test_severity_upgrade_low_to_critical(self):
        old = _make_decision(decision_id="dec_old", severity=Severity.LOW)
        new = _make_decision(decision_id="dec_new", severity=Severity.CRITICAL)

        result = diff_decisions(old, new)
        d = [d for d in result.diffs if d.field == "severity"][0]

        assert d.kind == "upgrade"
        assert d.old_value == "low"
        assert d.new_value == "critical"
        assert "low -> critical" in d.message

    def test_severity_downgrade_high_to_low(self):
        old = _make_decision(decision_id="dec_old", severity=Severity.HIGH)
        new = _make_decision(decision_id="dec_new", severity=Severity.LOW)

        result = diff_decisions(old, new)
        d = [d for d in result.diffs if d.field == "severity"][0]

        assert d.kind == "downgrade"
        assert d.old_value == "high"
        assert d.new_value == "low"

    def test_severity_unchanged(self):
        old = _make_decision(decision_id="dec_old", severity=Severity.MEDIUM)
        new = _make_decision(decision_id="dec_new", severity=Severity.MEDIUM)

        result = diff_decisions(old, new)
        d = [d for d in result.diffs if d.field == "severity"][0]

        assert d.kind == "unchanged"


class TestDiffAllowedField:

    def test_allowed_true_to_false_is_downgrade(self):
        old = _make_decision(decision_id="dec_old", allowed=True)
        new = _make_decision(decision_id="dec_new", allowed=False)

        result = diff_decisions(old, new)
        d = [d for d in result.diffs if d.field == "allowed"][0]

        assert d.kind == "downgrade"
        assert d.old_value is True
        assert d.new_value is False

    def test_allowed_false_to_true_is_upgrade(self):
        old = _make_decision(decision_id="dec_old", allowed=False)
        new = _make_decision(decision_id="dec_new", allowed=True)

        result = diff_decisions(old, new)
        d = [d for d in result.diffs if d.field == "allowed"][0]

        assert d.kind == "upgrade"
        assert d.old_value is False
        assert d.new_value is True


class TestDiffReasonField:

    def test_reason_changed(self):
        old = _make_decision(decision_id="dec_old", reason="Old reason")
        new = _make_decision(decision_id="dec_new", reason="New reason")

        result = diff_decisions(old, new)
        d = [d for d in result.diffs if d.field == "reason"][0]

        assert d.kind == "changed"
        assert d.old_value == "Old reason"
        assert d.new_value == "New reason"

    def test_reason_unchanged(self):
        old = _make_decision(decision_id="dec_old", reason="Same reason")
        new = _make_decision(decision_id="dec_new", reason="Same reason")

        result = diff_decisions(old, new)
        d = [d for d in result.diffs if d.field == "reason"][0]

        assert d.kind == "unchanged"


class TestDiffMatchedPolicyIds:

    def test_policy_ids_added(self):
        old = _make_decision(decision_id="dec_old", matched_policy_ids=["a"])
        new = _make_decision(decision_id="dec_new", matched_policy_ids=["a", "b"])

        result = diff_decisions(old, new)
        d = [d for d in result.diffs if d.field == "matched_policy_ids"][0]

        assert d.kind == "changed"
        assert "added: [b]" in d.message

    def test_policy_ids_removed(self):
        old = _make_decision(decision_id="dec_old", matched_policy_ids=["a", "b"])
        new = _make_decision(decision_id="dec_new", matched_policy_ids=["a"])

        result = diff_decisions(old, new)
        d = [d for d in result.diffs if d.field == "matched_policy_ids"][0]

        assert d.kind == "changed"
        assert "removed: [b]" in d.message

    def test_policy_ids_added_and_removed(self):
        old = _make_decision(decision_id="dec_old", matched_policy_ids=["a", "b"])
        new = _make_decision(decision_id="dec_new", matched_policy_ids=["b", "c"])

        result = diff_decisions(old, new)
        d = [d for d in result.diffs if d.field == "matched_policy_ids"][0]

        assert d.kind == "changed"
        assert "added: [c]" in d.message
        assert "removed: [a]" in d.message

    def test_policy_ids_unchanged(self):
        old = _make_decision(decision_id="dec_old", matched_policy_ids=["a", "b"])
        new = _make_decision(decision_id="dec_new", matched_policy_ids=["a", "b"])

        result = diff_decisions(old, new)
        d = [d for d in result.diffs if d.field == "matched_policy_ids"][0]

        assert d.kind == "unchanged"


class TestDiffOutputIsDeterministic:

    def test_output_order_is_fixed(self):
        old = _make_decision(decision_id="dec_old")
        new = _make_decision(
            decision_id="dec_new",
            decision=GovernanceDecisionType.BLOCK,
            allowed=False,
            severity=Severity.CRITICAL,
            reason="blocked",
            matched_policy_ids=["b"],
        )

        result = diff_decisions(old, new)

        fields = [d.field for d in result.diffs]
        expected = ["decision", "severity", "allowed", "reason", "matched_policy_ids"]
        assert fields == expected
        assert result.has_changes

    def test_same_inputs_produce_same_output(self):
        old = _make_decision(
            decision_id="dec_old",
            decision=GovernanceDecisionType.BLOCK,
            allowed=False,
            severity=Severity.HIGH,
        )
        new = _make_decision(
            decision_id="dec_new",
            decision=GovernanceDecisionType.WARN,
            allowed=True,
            severity=Severity.LOW,
        )

        r1 = diff_decisions(old, new)
        r2 = diff_decisions(old, new)

        assert r1.diffs == r2.diffs
        assert r1.has_changes == r2.has_changes
        assert r1.change_summary == r2.change_summary


class TestHasChangesProperty:

    def test_has_changes_true_when_any_diff_is_not_unchanged(self):
        old = _make_decision(decision_id="dec_old")
        new = _make_decision(decision_id="dec_new", reason="different")

        result = diff_decisions(old, new)
        assert result.has_changes

    def test_has_changes_false_when_all_unchanged(self):
        old = _make_decision(decision_id="dec_old")
        new = _make_decision(decision_id="dec_new")

        result = diff_decisions(old, new)
        assert not result.has_changes


class TestChangeSummary:

    def test_summary_lists_only_changes(self):
        old = _make_decision(decision_id="dec_old", reason="old reason")
        new = _make_decision(decision_id="dec_new", reason="new reason")

        result = diff_decisions(old, new)
        summary = result.change_summary

        assert "Reason changed" in summary
        assert "unchanged" not in summary

    def test_summary_when_no_changes(self):
        old = _make_decision(decision_id="dec_old")
        new = _make_decision(decision_id="dec_new")

        result = diff_decisions(old, new)
        assert result.change_summary == "No changes detected."
