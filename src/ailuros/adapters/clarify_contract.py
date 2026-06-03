from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class ClarifyGovernanceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    app: str
    action: str
    content_type: str
    risk_surface: str
    tool_requested: str
    context: dict[str, Any] = {}
    evidence_ids: list[str] = []
