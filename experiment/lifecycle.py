"""Experiment status transition validation."""
from __future__ import annotations

from dataclasses import dataclass, field

from .constants import EXP_TRANSITIONS


@dataclass
class TransitionResult:
    ok: bool
    errors: list[str] = field(default_factory=list)


def validate_experiment_transition(from_status: str, to_status: str) -> TransitionResult:
    errors: list[str] = []
    if from_status not in EXP_TRANSITIONS:
        errors.append(f"invalid from_status: {from_status!r}")
    if to_status not in ("planned", "running", "completed", "aborted"):
        errors.append(f"invalid to_status: {to_status!r}")
    if errors:
        return TransitionResult(False, errors)
    allowed = EXP_TRANSITIONS.get(from_status, frozenset())
    if to_status not in allowed:
        errors.append(
            f"illegal transition {from_status!r} → {to_status!r}; "
            f"allowed: {sorted(allowed) or 'none'}"
        )
    return TransitionResult(ok=len(errors) == 0, errors=errors)
