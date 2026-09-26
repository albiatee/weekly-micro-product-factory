"""Fixed checklist risk score in [0, 1]. Higher = riskier."""
from __future__ import annotations

from typing import Any


def compute_risk(
    *,
    experiment: dict[str, Any] | None,
    channel: str | None,
    template: str | None,
    allowed_channels: list[str],
    allowed_templates: list[str],
    budget_known: bool,
    snapshots_complete: bool,
) -> float:
    score = 0.0
    if not experiment or experiment.get("status") != "completed":
        score += 0.4
    if not snapshots_complete:
        score += 0.3
    if channel and channel not in allowed_channels:
        score += 0.4
    if template and template not in allowed_templates:
        score += 0.4
    if not budget_known:
        score += 0.2
    return min(1.0, score)
