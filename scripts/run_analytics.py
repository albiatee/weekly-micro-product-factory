#!/usr/bin/env python3
"""CLI: Phase 8 Analytics & Learning (deterministic, non-deciding)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from analytics.pipeline import generate_learning_records, run_analytics  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description="Run analytics / generate learning records")
    p.add_argument("--opportunity-id", default=None)
    p.add_argument("--period", default=None, help="Reserved for future filter (ignored in Phase 8)")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--json", action="store_true", help="Print JSON (default)")
    p.add_argument("--learn", action="store_true", help="Also generate LearningRecords")
    p.add_argument("--opportunities-dir", default=None)
    p.add_argument("--experiments-dir", default=None)
    p.add_argument("--decisions-dir", default=None)
    p.add_argument("--signals-dir", default=None)
    p.add_argument("--distribution-dir", default=None)
    p.add_argument("--analytics-dir", default=None)
    args = p.parse_args()

    kwargs = dict(
        opportunity_id=args.opportunity_id,
        opportunities_root=Path(args.opportunities_dir) if args.opportunities_dir else None,
        experiments_root=Path(args.experiments_dir) if args.experiments_dir else None,
        decisions_root=Path(args.decisions_dir) if args.decisions_dir else None,
        signals_root=Path(args.signals_dir) if args.signals_dir else None,
        distribution_root=Path(args.distribution_dir) if args.distribution_dir else None,
        analytics_root=Path(args.analytics_dir) if args.analytics_dir else None,
        dry_run=args.dry_run,
    )
    ares = run_analytics(**{k: v for k, v in kwargs.items() if k != "period"})
    out: dict = {"analytics": {"ok": ares.ok, "snapshot": ares.snapshot, "errors": ares.errors}}
    if args.learn:
        lres = generate_learning_records(
            opportunity_id=args.opportunity_id,
            opportunities_root=kwargs["opportunities_root"],
            experiments_root=kwargs["experiments_root"],
            decisions_root=kwargs["decisions_root"],
            distribution_root=kwargs["distribution_root"],
            analytics_root=kwargs["analytics_root"],
            dry_run=args.dry_run,
        )
        out["learning"] = {
            "ok": lres.ok,
            "learnings": lres.learnings,
            "errors": lres.errors,
        }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if ares.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
