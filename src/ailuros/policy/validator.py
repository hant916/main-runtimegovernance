from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import ValidationError

from ailuros.models import Policy, PolicyOperator
from ailuros.policy.errors import PolicyValidationError


class PolicyValidator:
    required_fields = {"policy_id", "version", "match", "severity"}

    def validate(self, data: dict[str, Any], source: Path | None = None) -> Policy:
        missing = self.required_fields - data.keys()
        if missing:
            raise PolicyValidationError(self._message(source, f"missing required field: {sorted(missing)[0]}"))
        self._validate_conditions(data.get("match", {}), source)
        self._validate_conditions(data.get("scope", {}), source)
        self._validate_conditions(data.get("requires_previous_steps", {}), source)
        try:
            return Policy.model_validate(data)
        except ValidationError as exc:
            raise PolicyValidationError(self._message(source, str(exc))) from exc

    def validate_many(
        self, policies: list[dict[str, Any]], sources: list[Path] | None = None
    ) -> list[Policy]:
        return [
            self.validate(policy, sources[index] if sources else None)
            for index, policy in enumerate(policies)
        ]

    def _validate_conditions(self, conditions: Any, source: Path | None) -> None:
        if not isinstance(conditions, dict):
            raise PolicyValidationError(self._message(source, "conditions must be an object"))
        for field, condition in conditions.items():
            if isinstance(condition, dict):
                for operator in condition:
                    try:
                        PolicyOperator(operator)
                    except ValueError as exc:
                        raise PolicyValidationError(
                            self._message(source, f"unknown operator for {field}: {operator}")
                        ) from exc

    def _message(self, source: Path | None, message: str) -> str:
        prefix = f"{source}: " if source is not None else ""
        return f"{prefix}{message}"
