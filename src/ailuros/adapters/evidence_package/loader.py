from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ailuros.core.evidence import EvidenceEvent, EvidencePackage


def _load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        msg = f"Invalid JSON in {path.name}: {e}"
        raise ValueError(msg) from e


def load_evidence_package(package_dir: str | Path) -> EvidencePackage:
    pkg_path = Path(package_dir)

    if not pkg_path.is_dir():
        msg = f"Evidence package directory not found: {pkg_path}"
        raise FileNotFoundError(msg)

    manifest_path = pkg_path / "manifest.json"
    if not manifest_path.is_file():
        msg = f"Missing manifest.json in evidence package: {pkg_path}"
        raise FileNotFoundError(msg)

    timeline_path = pkg_path / "timeline.json"
    if not timeline_path.is_file():
        msg = f"Missing timeline.json in evidence package: {pkg_path}"
        raise FileNotFoundError(msg)

    manifest = _load_json(manifest_path)
    raw_events = _load_json(timeline_path)

    events_data = raw_events if isinstance(raw_events, list) else raw_events.get("events", [])
    events = [EvidenceEvent(**ev) for ev in events_data]

    return EvidencePackage(
        source=manifest.get("source", ""),
        schema_version=manifest.get("schema_version", ""),
        run_id=manifest.get("run_id", ""),
        events=events,
        files={"manifest.json": manifest_path.name, "timeline.json": timeline_path.name},
        metadata=manifest.get("metadata", {}),
    )
