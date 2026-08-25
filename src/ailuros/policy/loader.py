from __future__ import annotations

import json
from pathlib import Path

from ailuros.models import Policy
from ailuros.policy.errors import PolicyValidationError
from ailuros.policy.validator import PolicyValidator


class PolicyLoader:
    def __init__(self, validator: PolicyValidator | None = None) -> None:
        self.validator = validator or PolicyValidator()

    def load_file(self, path: str | Path) -> Policy:
        source = Path(path)
        try:
            data = json.loads(source.read_text(encoding="utf-8"))
        except OSError as exc:
            raise PolicyValidationError(f"{source}: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise PolicyValidationError(f"{source}: invalid JSON: {exc}") from exc
        if not isinstance(data, dict):
            raise PolicyValidationError(f"{source}: policy file must contain a JSON object")
        return self.validator.validate(data, source)

    def load_files(self, paths: list[str | Path]) -> list[Policy]:
        return [self.load_file(path) for path in paths]

    def load_directory(self, path: str | Path, *, strict: bool = False) -> list[Policy]:
        source = Path(path)
        policies: list[Policy] = []
        errors: list[PolicyValidationError] = []
        for policy_path in sorted(source.glob("*.json")):
            try:
                policies.append(self.load_file(policy_path))
            except PolicyValidationError as exc:
                errors.append(exc)
                if strict:
                    raise
        if not policies and errors:
            raise errors[0]
        return policies
