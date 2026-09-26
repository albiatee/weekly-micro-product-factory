"""Fixed step order — no jumps."""
from __future__ import annotations

STEPS: list[str] = [
    "COLLECT",
    "QUALIFY",
    "OPPORTUNITY",
    "SELECT",
    "EXPERIMENT",
    "DECIDE",
    "PRODUCE",
    "BUILD",
    "PUBLISH",
    "MEASURE",
    "LEARN",
    "FEEDBACK",
]

_INDEX = {s: i for i, s in enumerate(STEPS)}


def allowed_next(current: str | None) -> str | None:
    if current is None:
        return STEPS[0]
    i = _INDEX.get(current)
    if i is None or i + 1 >= len(STEPS):
        return None
    return STEPS[i + 1]


def is_jump(from_step: str | None, to_step: str) -> bool:
    if from_step is None:
        return to_step != STEPS[0]
    exp = allowed_next(from_step)
    return exp != to_step


def steps_until(stop_after: str | None) -> list[str]:
    if not stop_after:
        return list(STEPS)
    if stop_after not in _INDEX:
        raise ValueError(f"unknown step: {stop_after}")
    return STEPS[: _INDEX[stop_after] + 1]
