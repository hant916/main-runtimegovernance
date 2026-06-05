from __future__ import annotations

from examples.evidence_demo import run_demo


class TestEvidenceDemo:
    def test_demo_runs_and_all_pipeline_steps_pass(self) -> None:
        result = run_demo()
        assert result["exported_count"] == 3
        assert result["evaluation_passed"] is True
        assert result["regression_passed"] is True
        assert result["regression_diff_detected"] is True
