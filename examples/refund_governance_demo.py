from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from pathlib import Path
from typing import Any
from uuid import uuid4

from ailuros import AilurosRuntime, Environment, EvidenceRecord
from ailuros.audit_package import export_audit_package_to_dir
from ailuros.evaluation.models import EvaluationCase, GovernanceDecisionExpectation
from ailuros.evaluation.service import EvaluationService
from ailuros.evidence.ingest import ingest_evidence
from ailuros.models import EvaluationFinding, EvaluationResult, Severity
from ailuros.runtime.clock import now_utc

HIGH_VALUE_POLICY = {
    "policy_id": "refund.high_value_requires_review",
    "version": "1.0.0",
    "decision": "require_review",
    "severity": "high",
    "enabled": True,
    "description": "Require human review for high-value refunds.",
    "match": {
        "tool_name": "refund.process",
        "arguments.amount_eur": {"gt": 300},
    },
    "reason": "Refund amount exceeds automated approval threshold.",
}

INVALID_PNR_POLICY = {
    "policy_id": "refund.invalid_pnr",
    "version": "1.0.0",
    "decision": "block",
    "severity": "high",
    "enabled": True,
    "description": "Block refunds with invalid PNR state.",
    "match": {
        "tool_name": "refund.process",
        "arguments.pnr_state": "invalid",
    },
    "reason": "Invalid PNR state prevents refund processing.",
}

FIXTURES = [
    {
        "case_id": "refund-low-eligible",
        "request_id": "REQ-001",
        "refund_amount": 120,
        "pnr_state": "valid",
        "expected_decision": "allow",
        "description": "Low-value refund with valid PNR should be allowed.",
    },
    {
        "case_id": "refund-high-eligible",
        "request_id": "REQ-002",
        "refund_amount": 850,
        "pnr_state": "valid",
        "expected_decision": "require_review",
        "description": "High-value refund with valid PNR requires review.",
    },
    {
        "case_id": "refund-invalid-pnr",
        "request_id": "REQ-003",
        "refund_amount": 50,
        "pnr_state": "invalid",
        "expected_decision": "block",
        "description": "Refund with invalid PNR should be blocked.",
    },
]


def run_demo(output_dir: Path) -> dict[str, Any]:
    tmp_dir = Path(tempfile.mkdtemp())
    try:
        policies_dir = tmp_dir / "policies"
        policies_dir.mkdir(parents=True, exist_ok=True)
        for name, data in [
            ("high_value.json", HIGH_VALUE_POLICY),
            ("invalid_pnr.json", INVALID_PNR_POLICY),
        ]:
            (policies_dir / name).write_text(json.dumps(data, indent=2), encoding="utf-8")

        runtime = AilurosRuntime(
            agent_id="refund_governance_demo",
            environment=Environment.DEVELOPMENT,
            storage_path=str(tmp_dir / "runtime.sqlite"),
            policies=[str(p) for p in sorted(policies_dir.glob("*.json"))],
        )

        run = runtime.start_run("Refund governance demo: processing fixture cases")

        fixture_decisions: list[dict[str, Any]] = []
        tool_name = "refund.process"

        for fixture in FIXTURES:
            arguments = {
                "amount_eur": fixture["refund_amount"],
                "pnr_state": fixture["pnr_state"],
            }

            decision = runtime.before_tool_call(run.run_id, tool_name, arguments)

            if decision.allowed:
                runtime.after_tool_call(
                    run.run_id,
                    tool_name,
                    arguments,
                    result={"refund_processed": True, "amount_eur": fixture["refund_amount"]},
                )

            evidence_record = EvidenceRecord(
                version="1.0.0",
                run_id=run.run_id,
                event_type="refund_governance",
                payload={
                    "request_id": fixture["request_id"],
                    "case_id": fixture["case_id"],
                    "refund_amount": fixture["refund_amount"],
                    "pnr_state": fixture["pnr_state"],
                    "policy_decision": decision.decision.value,
                    "policy_reason": decision.reason,
                    "simulated_tool_name": tool_name,
                    "evaluation_result": (
                        "passed"
                        if decision.decision.value == fixture["expected_decision"]
                        else "failed"
                    ),
                    "final_status": "completed",
                },
                timestamp=now_utc(),
            )
            ingest_evidence(runtime.storage, evidence_record)

            fixture_decisions.append({
                "case_id": fixture["case_id"],
                "expected_decision": fixture["expected_decision"],
                "actual_decision": decision.decision.value,
                "reason": decision.reason,
            })

        events = runtime.list_events(run.run_id)
        eval_cases = [
            EvaluationCase(
                id=f["case_id"],
                name=f["description"],
                expectations=[GovernanceDecisionExpectation(decision=f["expected_decision"])],
            )
            for f in FIXTURES
        ]
        eval_service = EvaluationService()
        eval_results = eval_service.evaluate(events, eval_cases)
        runtime.storage.save_evaluation(
            EvaluationResult(
                evaluation_id=f"eval_{uuid4().hex}",
                run_id=run.run_id,
                evaluator="refund_governance_demo",
                passed=all(r.passed for r in eval_results),
                findings=[
                    EvaluationFinding(
                        finding_id=f"finding_{uuid4().hex}",
                        severity=Severity.HIGH,
                        message=f"{r.case_id}: {failure.message}",
                        metadata={
                            "case_id": r.case_id,
                            "expectation_type": failure.expectation_type,
                        },
                    )
                    for r in eval_results
                    for failure in r.failures
                ],
                metadata={
                    "case_results": [
                        {"case_id": r.case_id, "passed": r.passed} for r in eval_results
                    ],
                },
                created_at=now_utc(),
            )
        )

        runtime.complete_run(
            run.run_id,
            output={
                "fixtures_processed": len(FIXTURES),
                "evaluations_passed": sum(1 for r in eval_results if r.passed),
                "evaluations_failed": sum(1 for r in eval_results if not r.passed),
            },
        )

        pkg_dir = export_audit_package_to_dir(runtime.storage, run.run_id, output_dir)

        return {
            "audit_package_dir": pkg_dir,
            "run_id": run.run_id,
            "fixture_decisions": fixture_decisions,
            "eval_results": [
                {"case_id": r.case_id, "passed": r.passed} for r in eval_results
            ],
        }
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Refund governance demo")
    parser.add_argument(
        "--output-dir",
        required=True,
        type=Path,
        help="Directory to write the audit package to.",
    )
    args = parser.parse_args()

    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    result = run_demo(output_dir)
    print(f"Audit package written to: {result['audit_package_dir']}")

    for fd in result["fixture_decisions"]:
        status = "PASS" if fd["expected_decision"] == fd["actual_decision"] else "FAIL"
        print(f"  [{status}] {fd['case_id']}: {fd['actual_decision']}")


if __name__ == "__main__":
    main()
