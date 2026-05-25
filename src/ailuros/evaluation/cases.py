from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from ailuros.evaluation.models import EvaluationCase


class EvaluationCaseLoadError(ValueError):
    pass


def load_evaluation_cases(path: str | Path) -> list[EvaluationCase]:
    case_path = Path(path)
    try:
        raw = json.loads(case_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise EvaluationCaseLoadError(f"could not read evaluation case file: {case_path}") from exc
    except json.JSONDecodeError as exc:
        raise EvaluationCaseLoadError(f"invalid JSON in evaluation case file: {case_path}") from exc

    try:
        return _parse_cases(raw)
    except ValidationError as exc:
        raise EvaluationCaseLoadError(
            f"invalid evaluation case file: {case_path}: {exc.errors()[0]['msg']}"
        ) from exc


def _parse_cases(raw: Any) -> list[EvaluationCase]:
    if isinstance(raw, list):
        return [EvaluationCase.model_validate(item) for item in raw]
    return [EvaluationCase.model_validate(raw)]
