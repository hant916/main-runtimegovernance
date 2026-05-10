from __future__ import annotations

from typing import Any


class MissingValue:
    pass


MISSING = MissingValue()


def get_by_path(value: Any, path: str) -> Any:
    current = value
    for part in path.split("."):
        if isinstance(current, dict):
            if part not in current:
                return MISSING
            current = current[part]
            continue
        if hasattr(current, part):
            current = getattr(current, part)
            continue
        return MISSING
    return current
