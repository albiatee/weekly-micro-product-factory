#!/usr/bin/env python3
"""P8 Closed Autonomous Loop CLI."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from orchestrator.closed_loop import run_closed_loop  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description="P8 closed factory loop")
    p.add_argument("--dry-run", action="store_true", default=False)
    p.add_argument("--live", action="store_true", help="Allow non-dry-run (still no public publish)")
    p.add_argument("--opportunity-id")
    p.add_argument("--metrics-json", help='e.g. {"signups":7}')
    p.add_argument("--force-enabled", action="store_true")
    p.add_argument("--no-persist", action="store_true")
    args = p.parse_args()
    dry_run = not args.live if not args.dry_run else True
    if args.dry_run:
        dry_run = True
    metrics = json.loads(args.metrics_json) if args.metrics_json else None
    res = run_closed_loop(
        dry_run=dry_run,
        metrics=metrics,
        opportunity_id=args.opportunity_id,
        force_enabled=args.force_enabled,
        persist=not args.no_persist,
    )
    print(
        json.dumps(
            {
                "ok": res.ok,
                "errors": res.errors,
                "cycle_id": res.cycle.get("id"),
                "state": res.cycle.get("state"),
                "status": res.cycle.get("status"),
                "outcome": res.cycle.get("outcome"),
                "dry_run": res.cycle.get("dry_run"),
                "live_publish": res.cycle.get("live_publish"),
                "failure_reason": res.cycle.get("failure_reason"),
                "refs": res.cycle.get("refs"),
                "decision_ids": res.cycle.get("decision_ids"),
                "build_ids": res.cycle.get("build_ids"),
                "analytics_ids": res.cycle.get("analytics_ids"),
                "learning_ids": res.cycle.get("learning_ids"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if res.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
