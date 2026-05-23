from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from ailuros.models import RuntimeEvent, RuntimeEventType


class ExpectedPath(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    path_id: str
    required_tool_calls: list[str] = Field(default_factory=list)
    optional_tool_calls: list[str] = Field(default_factory=list)
    forbidden_tool_calls: list[str] = Field(default_factory=list)


class PathValidationResult(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    path_id: str
    valid: bool
    missing_required: list[str]
    observed_required: list[str]
    forbidden_observed: list[str]
    unexpected_tool_calls: list[str]
    reason: str


class PathValidator:
    @staticmethod
    def validate(expected_path: ExpectedPath, events: list[RuntimeEvent]) -> PathValidationResult:
        if not isinstance(expected_path, ExpectedPath):
            raise TypeError("expected_path must be an ExpectedPath")
        if not isinstance(events, list):
            raise TypeError("events must be a list of RuntimeEvent objects")
        if not all(isinstance(event, RuntimeEvent) for event in events):
            raise TypeError("events must be a list of RuntimeEvent objects")

        tool_events = [
            event for event in events if event.event_type == RuntimeEventType.TOOL_CALL_REQUESTED
        ]
        if tool_events and all(event.sequence is not None for event in tool_events):
            tool_events = sorted(
                tool_events,
                key=lambda event: event.sequence if event.sequence is not None else 0,
            )

        observed_tool_calls: list[str] = []
        malformed_reasons: list[str] = []
        for event in tool_events:
            tool_name = event.payload.get("tool_name")
            if not isinstance(tool_name, str):
                malformed_reasons.append(f"{event.event_id} missing payload.tool_name")
                continue
            observed_tool_calls.append(tool_name)

        observed_required: list[str] = []
        missing_required: list[str] = []
        search_from = 0
        for required_tool_call in expected_path.required_tool_calls:
            try:
                found_at = observed_tool_calls.index(required_tool_call, search_from)
            except ValueError:
                missing_required.append(required_tool_call)
                continue
            observed_required.append(required_tool_call)
            search_from = found_at + 1

        forbidden_set = set(expected_path.forbidden_tool_calls)
        forbidden_observed = [
            tool_call for tool_call in observed_tool_calls if tool_call in forbidden_set
        ]

        expected_tool_calls = (
            set(expected_path.required_tool_calls)
            | set(expected_path.optional_tool_calls)
            | forbidden_set
        )
        unexpected_tool_calls = [
            tool_call for tool_call in observed_tool_calls if tool_call not in expected_tool_calls
        ]

        reasons: list[str] = []
        if missing_required:
            reasons.append("missing required tool call")
        if forbidden_observed:
            reasons.append("forbidden tool call observed")
        reasons.extend(malformed_reasons)

        return PathValidationResult(
            path_id=expected_path.path_id,
            valid=not missing_required and not forbidden_observed and not malformed_reasons,
            missing_required=missing_required,
            observed_required=observed_required,
            forbidden_observed=forbidden_observed,
            unexpected_tool_calls=unexpected_tool_calls,
            reason="; ".join(reasons) if reasons else "valid",
        )
