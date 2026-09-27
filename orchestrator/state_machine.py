"""P8 cycle state machine — deterministic transitions only."""
from __future__ import annotations

STATES = (
    "created",
    "discovering",
    "opportunity",
    "experimenting",
    "deciding",
    "building",
    "measuring",
    "learning",
    "completed",
    "failed",
    "killed",
)

# Legal edges only
TRANSITIONS: dict[str, frozenset[str]] = {
    "created": frozenset({"discovering", "failed", "killed"}),
    "discovering": frozenset({"opportunity", "failed", "killed"}),
    "opportunity": frozenset({"experimenting", "failed", "killed", "completed"}),
    "experimenting": frozenset({"deciding", "failed", "killed"}),
    "deciding": frozenset({"building", "learning", "completed", "failed", "killed"}),
    # deciding → building only when execute; → completed/learning for kill/iterate/no_decision
    "building": frozenset({"measuring", "failed", "killed"}),
    "measuring": frozenset({"learning", "failed", "killed"}),
    "learning": frozenset({"completed", "failed", "killed"}),
    "completed": frozenset(),
    "failed": frozenset(),
    "killed": frozenset(),
}


def can_transition(from_state: str, to_state: str) -> bool:
    return to_state in TRANSITIONS.get(from_state, frozenset())


def transition(from_state: str, to_state: str) -> tuple[bool, str]:
    if from_state == to_state:
        return True, from_state
    if not can_transition(from_state, to_state):
        return False, f"illegal transition {from_state!r} → {to_state!r}"
    return True, to_state
