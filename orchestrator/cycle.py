"""Cycle identity and record helpers."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any


def new_cycle_id() -> str:
    return f"cyc_{uuid.uuid4().hex[:16]}"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def new_cycle_record(
    *,
    policy_id: str,
    policy_version: str,
    dry_run: bool,
) -> dict[str, Any]:
    now = _now()
    return {
        "id": new_cycle_id(),
        "status": "running",
        "policy_id": policy_id,
        "policy_version": policy_version,
        "dry_run": dry_run,
        "created_at": now,
        "updated_at": now,
        "current_step": None,
        "completed_steps": [],
        "step_log": [],
        "selection": {"opportunity_ids": [], "scores": {}},
        "experiment_ids": [],
        "decision_ids": [],
        "counters": {
            "opportunities": 0,
            "experiments": 0,
            "publishes": 0,
            "iterations": 0,
            "spend": 0,
        },
        "refs": {},
        "abort_reason": None,
    }
