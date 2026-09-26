"""Hard ceilings — cannot be overridden by Policy."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class GuardrailResult:
    ok: bool
    blocks: list[str] = field(default_factory=list)


def check_produce_path(
    *,
    verdict: str,
    dry_run: bool,
    criteria_snapshot: Any,
    metrics_snapshot: Any,
    build_template: str,
    config: dict[str, Any],
) -> GuardrailResult:
    blocks: list[str] = []
    if dry_run:
        blocks.append("dry_run")
    if verdict != "execute":
        blocks.append(f"verdict_not_execute:{verdict}")
    if not criteria_snapshot:
        blocks.append("missing_criteria_snapshot")
    if metrics_snapshot is None:
        blocks.append("missing_metrics_snapshot")
    allowed = list(config.get("allowed_templates") or [])
    if build_template not in allowed:
        blocks.append(f"template_not_allowed:{build_template}")
    return GuardrailResult(ok=len(blocks) == 0, blocks=blocks)


def check_publish(
    *,
    dry_run: bool,
    channel: str,
    config: dict[str, Any],
    publishes_this_cycle: int,
    publishes_this_week: int,
) -> GuardrailResult:
    blocks: list[str] = []
    if dry_run:
        blocks.append("dry_run")
    allowed = list(config.get("allowed_channels") or [])
    if channel not in allowed:
        blocks.append(f"channel_not_allowed:{channel}")
    if publishes_this_cycle >= int(config.get("max_publishes_per_cycle", 1)):
        blocks.append("max_publishes_per_cycle")
    if publishes_this_week >= int(config.get("max_publishes_per_week", 3)):
        blocks.append("max_publishes_per_week")
    return GuardrailResult(ok=len(blocks) == 0, blocks=blocks)
