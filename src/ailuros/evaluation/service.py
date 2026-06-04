from ailuros.evaluation.models import (
    AllowedToolExpectation,
    BlockedToolExpectation,
    EvaluationCase,
    EvaluationEvidence,
    EvaluationExpectation,
    EvaluationFailure,
    EvaluationResult,
    EventSequenceContainsExpectation,
    EvidenceEventExpectation,
    GovernanceDecisionExpectation,
    PathValidationExpectation,
    ToolNotExecutedExpectation,
)
from ailuros.models import RuntimeEvent, RuntimeEventType


class EvaluationService:
    def evaluate(
        self, events: list[RuntimeEvent], cases: list[EvaluationCase]
    ) -> list[EvaluationResult]:
        results: list[EvaluationResult] = []
        for case in cases:
            failures: list[EvaluationFailure] = []
            evidence: list[EvaluationEvidence] = []
            for expectation in case.expectations:
                expectation_failures, expectation_evidence = self._evaluate_expectation(
                    events, expectation
                )
                failures.extend(expectation_failures)
                evidence.extend(expectation_evidence)
            results.append(
                EvaluationResult(
                    case_id=case.id,
                    passed=not failures,
                    failures=failures,
                    evidence=evidence,
                )
            )
        return results

    def _evaluate_expectation(
        self, events: list[RuntimeEvent], expectation: EvaluationExpectation
    ) -> tuple[list[EvaluationFailure], list[EvaluationEvidence]]:
        if isinstance(expectation, GovernanceDecisionExpectation):
            return self._governance_decision(events, expectation), self._decision_evidence(
                events, expectation
            )
        if isinstance(expectation, BlockedToolExpectation):
            return self._blocked_tool(events, expectation), self._blocked_tool_evidence(
                events, expectation
            )
        if isinstance(expectation, AllowedToolExpectation):
            return self._allowed_tool(events, expectation), self._allowed_tool_evidence(
                events, expectation
            )
        if isinstance(expectation, ToolNotExecutedExpectation):
            return self._tool_not_executed(events, expectation)
        if isinstance(expectation, PathValidationExpectation):
            return self._path_validation(events, expectation), self._path_validation_evidence(
                events, expectation
            )
        if isinstance(expectation, EventSequenceContainsExpectation):
            return self._event_sequence_contains(events, expectation)
        if isinstance(expectation, EvidenceEventExpectation):
            return self._evidence_event(events, expectation), self._evidence_event_evidence(
                events, expectation
            )
        raise TypeError(f"Unsupported evaluation expectation type: {type(expectation).__name__}")

    def _governance_decision(
        self, events: list[RuntimeEvent], expectation: GovernanceDecisionExpectation
    ) -> list[EvaluationFailure]:
        matches = self._matching_decisions(events, expectation)
        if matches:
            return []
        actual = [
            {
                "decision": event.payload.get("decision"),
                "allowed": event.payload.get("allowed"),
                "severity": event.payload.get("severity"),
            }
            for event in events
            if event.event_type == RuntimeEventType.GOVERNANCE_DECISION
        ]
        return [
            EvaluationFailure(
                expectation_type=expectation.type,
                message=(
                    "Expected governance decision "
                    f"decision={expectation.decision!r}, "
                    f"allowed={expectation.allowed!r}, "
                    f"severity={expectation.severity!r}; "
                    f"actual={actual or 'missing'}"
                ),
            )
        ]

    def _decision_evidence(
        self, events: list[RuntimeEvent], expectation: GovernanceDecisionExpectation
    ) -> list[EvaluationEvidence]:
        match = self._first(self._matching_decisions(events, expectation))
        if not match:
            return []
        return [self._evidence(expectation.type, match, "Matched governance decision.")]

    def _blocked_tool(
        self, events: list[RuntimeEvent], expectation: BlockedToolExpectation
    ) -> list[EvaluationFailure]:
        if self._matching_blocked_tools(events, expectation):
            return []
        actual = [
            event.payload.get("tool_name")
            for event in events
            if event.event_type == RuntimeEventType.TOOL_CALL_BLOCKED
        ]
        return [
            EvaluationFailure(
                expectation_type=expectation.type,
                message=(
                    f"Expected blocked tool {expectation.tool_name!r}; "
                    f"actual={actual or 'missing'}"
                ),
            )
        ]

    def _blocked_tool_evidence(
        self, events: list[RuntimeEvent], expectation: BlockedToolExpectation
    ) -> list[EvaluationEvidence]:
        match = self._first(self._matching_blocked_tools(events, expectation))
        if not match:
            return []
        return [self._evidence(expectation.type, match, "Matched blocked tool call.")]

    def _allowed_tool(
        self, events: list[RuntimeEvent], expectation: AllowedToolExpectation
    ) -> list[EvaluationFailure]:
        if self._matching_allowed_tools(events, expectation.tool_name):
            return []
        actual = [
            event.payload.get("tool_name")
            for event in events
            if event.event_type
            in {RuntimeEventType.TOOL_CALL_EXECUTED, RuntimeEventType.TOOL_RESULT_RECEIVED}
        ]
        return [
            EvaluationFailure(
                expectation_type=expectation.type,
                message=(
                    f"Expected allowed/executed tool {expectation.tool_name!r}; "
                    f"actual={actual or 'missing'}"
                ),
            )
        ]

    def _allowed_tool_evidence(
        self, events: list[RuntimeEvent], expectation: AllowedToolExpectation
    ) -> list[EvaluationEvidence]:
        match = self._first(self._matching_allowed_tools(events, expectation.tool_name))
        if not match:
            return []
        return [self._evidence(expectation.type, match, "Matched allowed tool evidence.")]

    def _tool_not_executed(
        self, events: list[RuntimeEvent], expectation: ToolNotExecutedExpectation
    ) -> tuple[list[EvaluationFailure], list[EvaluationEvidence]]:
        blocked_index = self._first_index(
            events,
            RuntimeEventType.TOOL_CALL_BLOCKED,
            expectation.tool_name,
        )
        if blocked_index is None:
            return (
                [
                    EvaluationFailure(
                        expectation_type=expectation.type,
                        message=(
                            f"Expected blocking evidence for tool {expectation.tool_name!r}; "
                            "actual=missing"
                        ),
                    )
                ],
                [],
            )
        blocker = events[blocked_index]
        for event in events[blocked_index + 1 :]:
            if self._is_tool_execution_evidence(event, expectation.tool_name):
                return (
                    [
                        EvaluationFailure(
                            expectation_type=expectation.type,
                            message=(
                                f"Expected tool {expectation.tool_name!r} not to execute "
                                f"after block; actual={event.event_type.value} "
                                f"at sequence={event.sequence!r}"
                            ),
                        )
                    ],
                    [
                        self._evidence(expectation.type, blocker, "Matched blocking decision."),
                        self._evidence(
                            expectation.type, event, "Found forbidden execution after block."
                        ),
                    ],
                )
        return [], [
            self._evidence(expectation.type, blocker, "Matched block with no later execution.")
        ]

    def _path_validation(
        self, events: list[RuntimeEvent], expectation: PathValidationExpectation
    ) -> list[EvaluationFailure]:
        if self._matching_path_validations(events, expectation):
            return []
        actual = [
            {"path_id": event.payload.get("path_id"), "valid": event.payload.get("valid")}
            for event in events
            if event.event_type == RuntimeEventType.PATH_VALIDATION_RESULT
        ]
        return [
            EvaluationFailure(
                expectation_type=expectation.type,
                message=(
                    f"Expected path validation path_id={expectation.path_id!r}, "
                    f"valid={expectation.valid!r}; actual={actual or 'missing'}"
                ),
            )
        ]

    def _path_validation_evidence(
        self, events: list[RuntimeEvent], expectation: PathValidationExpectation
    ) -> list[EvaluationEvidence]:
        match = self._first(self._matching_path_validations(events, expectation))
        if not match:
            return []
        return [self._evidence(expectation.type, match, "Matched path validation result.")]

    def _event_sequence_contains(
        self, events: list[RuntimeEvent], expectation: EventSequenceContainsExpectation
    ) -> tuple[list[EvaluationFailure], list[EvaluationEvidence]]:
        matched: list[RuntimeEvent] = []
        cursor = 0
        for event_type in expectation.event_types:
            for index in range(cursor, len(events)):
                if events[index].event_type == event_type:
                    matched.append(events[index])
                    cursor = index + 1
                    break
            else:
                actual = [event.event_type.value for event in events]
                return (
                    [
                        EvaluationFailure(
                            expectation_type=expectation.type,
                            message=(
                                "Expected event sequence to contain "
                                f"{[item.value for item in expectation.event_types]!r} "
                                f"in order; actual={actual!r}"
                            ),
                        )
                    ],
                    [
                        self._evidence(expectation.type, event, "Matched event in sequence.")
                        for event in matched
                    ],
                )
        return [], [
            self._evidence(expectation.type, event, "Matched event in sequence.")
            for event in matched
        ]

    def _matching_decisions(
        self, events: list[RuntimeEvent], expectation: GovernanceDecisionExpectation
    ) -> list[RuntimeEvent]:
        return [
            event
            for event in events
            if event.event_type == RuntimeEventType.GOVERNANCE_DECISION
            and self._matches_optional(event.payload.get("decision"), expectation.decision)
            and self._matches_optional(event.payload.get("allowed"), expectation.allowed)
            and self._matches_optional(event.payload.get("severity"), expectation.severity)
        ]

    def _matching_blocked_tools(
        self, events: list[RuntimeEvent], expectation: BlockedToolExpectation
    ) -> list[RuntimeEvent]:
        return [
            event
            for event in events
            if event.event_type == RuntimeEventType.TOOL_CALL_BLOCKED
            and event.payload.get("tool_name") == expectation.tool_name
            and self._matches_optional(event.payload.get("decision"), expectation.decision)
        ]

    def _matching_allowed_tools(
        self, events: list[RuntimeEvent], tool_name: str
    ) -> list[RuntimeEvent]:
        return [event for event in events if self._is_tool_execution_evidence(event, tool_name)]

    def _matching_path_validations(
        self, events: list[RuntimeEvent], expectation: PathValidationExpectation
    ) -> list[RuntimeEvent]:
        return [
            event
            for event in events
            if event.event_type == RuntimeEventType.PATH_VALIDATION_RESULT
            and event.payload.get("valid") is expectation.valid
            and self._matches_optional(event.payload.get("path_id"), expectation.path_id)
        ]

    def _is_tool_execution_evidence(self, event: RuntimeEvent, tool_name: str) -> bool:
        return (
            event.event_type
            in {RuntimeEventType.TOOL_CALL_EXECUTED, RuntimeEventType.TOOL_RESULT_RECEIVED}
            and event.payload.get("tool_name") == tool_name
        )

    def _first_index(
        self, events: list[RuntimeEvent], event_type: RuntimeEventType, tool_name: str
    ) -> int | None:
        for index, event in enumerate(events):
            if event.event_type == event_type and event.payload.get("tool_name") == tool_name:
                return index
        return None

    def _evidence(
        self, expectation_type: str, event: RuntimeEvent, message: str
    ) -> EvaluationEvidence:
        return EvaluationEvidence(
            expectation_type=expectation_type,
            event_type=event.event_type,
            sequence=event.sequence,
            message=message,
        )

    def _matches_optional(self, actual: object, expected: object | None) -> bool:
        return expected is None or actual == expected

    def _evidence_event(
        self, events: list[RuntimeEvent], expectation: EvidenceEventExpectation
    ) -> list[EvaluationFailure]:
        if self._matching_evidence_events(events, expectation):
            return []
        actual = [
            {
                "event_type": event.payload.get("event_type"),
                "version": event.payload.get("version"),
            }
            for event in events
            if event.event_type in {RuntimeEventType.EVIDENCE, RuntimeEventType.EXTERNAL_EVIDENCE}
        ]
        return [
            EvaluationFailure(
                expectation_type=expectation.type,
                message=(
                    "Expected evidence event "
                    f"evidence_event_type={expectation.evidence_event_type!r}, "
                    f"version={expectation.version!r}, "
                    f"payload_contains={expectation.payload_contains!r}; "
                    f"actual={actual or 'missing'}"
                ),
            )
        ]

    def _evidence_event_evidence(
        self, events: list[RuntimeEvent], expectation: EvidenceEventExpectation
    ) -> list[EvaluationEvidence]:
        match = self._first(self._matching_evidence_events(events, expectation))
        if not match:
            return []
        return [self._evidence(expectation.type, match, "Matched evidence event.")]

    def _matching_evidence_events(
        self, events: list[RuntimeEvent], expectation: EvidenceEventExpectation
    ) -> list[RuntimeEvent]:
        return [
            event
            for event in events
            if event.event_type in {RuntimeEventType.EVIDENCE, RuntimeEventType.EXTERNAL_EVIDENCE}
            and self._matches_optional(
                event.payload.get("event_type"), expectation.evidence_event_type
            )
            and self._matches_optional(event.payload.get("version"), expectation.version)
            and self._matches_payload_contains(event.payload, expectation.payload_contains)
        ]

    def _matches_payload_contains(
        self, actual: dict[str, object], expected: dict[str, object] | None
    ) -> bool:
        if expected is None:
            return True
        return all(
            key in actual and actual[key] == value for key, value in expected.items()
        )

    def _first(self, events: list[RuntimeEvent]) -> RuntimeEvent | None:
        return events[0] if events else None
