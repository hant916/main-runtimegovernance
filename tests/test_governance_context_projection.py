from __future__ import annotations

import inspect
from datetime import UTC, datetime

from ailuros import projection
from ailuros.projection import build_execution_projection


def _event(event_id: str, payload: dict[str, object]) -> dict[str, object]:
    return {
        "event_id": event_id,
        "event_type": "governance_context",
        "timestamp": datetime(2026, 1, 1, tzinfo=UTC),
        "payload": payload,
    }


def test_everrun_like_context_projects_explicit_refs_and_pointers() -> None:
    projection_result = build_execution_projection(
        "run-everrun-like",
        "everrun-like",
        [
            _event(
                "evt-context-1",
                {
                    "principal_ref": "principal:operator-17",
                    "workflow_ref": "workflow:release",
                    "invocation_ref": "invocation:8043",
                    "policy_snapshot_ref": "policy:2026-01-01",
                    "source_pointers": ["evidence://governance/8043"],
                },
            )
        ],
    )

    assert projection_result.governance_context is not None
    context = projection_result.governance_context
    assert context.principal_ref == "principal:operator-17"
    assert context.workflow_ref == "workflow:release"
    assert context.invocation_ref == "invocation:8043"
    assert context.policy_snapshot_ref == "policy:2026-01-01"
    assert context.source_pointers == ["evt-context-1", "evidence://governance/8043"]
    assert context.inconsistencies == []
    assert [ref.event_id for ref in projection_result.evidence_refs] == ["evt-context-1"]


def test_generic_producer_projects_only_explicit_context_without_inference() -> None:
    projection_result = build_execution_projection(
        "run-generic-42",
        "generic-mcp-workflow",
        [
            _event(
                "evt-context-2",
                {
                    "workflow_ref": "workflow:generic-ingest",
                    "backend": "untrusted-backend-value",
                    "role": "untrusted-role-value",
                },
            )
        ],
    )

    assert projection_result.governance_context is not None
    context = projection_result.governance_context
    assert context.principal_ref is None
    assert context.workflow_ref == "workflow:generic-ingest"
    assert context.invocation_ref is None
    assert context.policy_snapshot_ref is None


def test_conflicting_explicit_context_is_reported_without_last_write_wins() -> None:
    projection_result = build_execution_projection(
        "run-conflict",
        "source-neutral",
        [
            _event("evt-context-3", {"principal_ref": "principal:alice"}),
            _event("evt-context-4", {"principal_ref": "principal:bob"}),
        ],
    )

    assert projection_result.governance_context is not None
    context = projection_result.governance_context
    assert context.principal_ref is None
    assert len(context.inconsistencies) == 1
    conflict = context.inconsistencies[0]
    assert conflict.field == "principal_ref"
    assert conflict.values == ["principal:alice", "principal:bob"]
    assert conflict.source_pointers == ["evt-context-3", "evt-context-4"]


def test_absent_context_fields_remain_unknown() -> None:
    projection_result = build_execution_projection(
        "run-absent-context",
        "generic-producer",
        [_event("evt-context-5", {"run_id": "not-an-invocation-ref"})],
    )

    assert projection_result.governance_context is None


def test_governance_context_projector_has_no_producer_identity_branch() -> None:
    source = inspect.getsource(projection._project_governance_context).lower()

    assert "everrun" not in source
    assert "generic-mcp-workflow" not in source
    assert "source" not in inspect.signature(
        projection._project_governance_context
    ).parameters
