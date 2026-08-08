from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

_AUDIT_PACKAGE_FILES = [
    "manifest.json",
    "run.json",
    "timeline.jsonl",
    "decisions.json",
    "evaluations.json",
    "regressions.json",
    "summary.md",
]


@dataclass(frozen=True)
class AuditPackage:
    path: Path
    manifest: Any
    run: Any
    timeline: list[Any]
    decisions: Any
    evaluations: Any
    regressions: Any
    summary: str


@dataclass(frozen=True)
class PackageValidationResult:
    valid: bool
    decision: str
    reasons: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "decision": self.decision,
            "reasons": self.reasons,
        }


class AuditPackageLoadError(ValueError):
    def __init__(self, reasons: list[str]) -> None:
        self.reasons = reasons
        super().__init__("; ".join(reasons))
