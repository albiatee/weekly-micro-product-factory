#!/usr/bin/env python3
"""Run one orchestrator cycle (default: dry-run until DECIDE)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from orchestrator.runner import run_cycle  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description="Autonomous factory orchestrator cycle")
    p.add_argument("--dry-run", action="store_true", default=True)
    p.add_argument("--live", action="store_true", help="Disable dry-run (still needs ORCHESTRATOR_ENABLED)")
    p.add_argument("--stop-after", default="DECIDE", help="Last step to run")
    p.add_argument("--force-enabled", action="store_true", help="Test helper: ignore kill switch for dry paths")
    p.add_argument("--no-persist", action="store_true")
    args = p.parse_args()
    dry = not args.live
    cycle = run_cycle(
        dry_run=dry,
        stop_after=args.stop_after,
        force_enabled=args.force_enabled or dry,
        persist=not args.no_persist,
    )
    print(json.dumps({
        "cycle_id": cycle.get("id"),
        "status": cycle.get("status"),
        "dry_run": cycle.get("dry_run"),
        "completed_steps": cycle.get("completed_steps"),
        "selection": cycle.get("selection"),
        "refs": cycle.get("refs"),
        "abort_reason": cycle.get("abort_reason"),
        "step_log_tail": (cycle.get("step_log") or [])[-4:],
    }, ensure_ascii=False, indent=2))
    return 0 if cycle.get("status") in ("completed", "aborted") else 1


if __name__ == "__main__":
    raise SystemExit(main())
