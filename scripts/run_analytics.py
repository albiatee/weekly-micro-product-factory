#!/usr/bin/env python3
"""CLI: Phase 8 Analytics & Learning (observational only)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from analytics.pipeline import generate_learning_records, run_analytics  # noqa: E402
from analytics.store import list_learnings, load_index  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description="Analytics & Learning (no lifecycle mutation)")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--opportunity-id", default=None)
    p.add_argument("--opportunities-dir", default=None)
    p.add_argument("--experiments-dir", default=None)
    p.add_argument("--decisions-dir", default=None)
    p.add_argument("--signals-dir", default=None)
    p.add_argument("--distribution-dir", default=None)
    p.add_argument("--production-dir", default=None)
    p.add_argument("--analytics-dir", default=None)
    sub = p.add_subparsers(dest="cmd")

    sub.add_parser("summary", help="Full analytics snapshot")
    sub.add_parser("funnel", help="Lifecycle funnel counts")
    sub.add_parser("inspect", help="Latest stored snapshot")
    learn = sub.add_parser("learn", help="Generate LearningRecords")
    learn.add_argument("--list", action="store_true", dest="list_only")
    li = sub.add_parser("learning-inspect")
    li.add_argument("--learning-id", required=True)

    # legacy flags without subcommand
    p.add_argument("--learn", action="store_true", help="(legacy) also generate learnings")
    p.add_argument("--json", action="store_true", default=True)
    p.add_argument("--period", default=None, help="Reserved / ignored")

    args = p.parse_args()
    roots = dict(
        opportunity_id=args.opportunity_id,
        opportunities_root=Path(args.opportunities_dir) if args.opportunities_dir else None,
        experiments_root=Path(args.experiments_dir) if args.experiments_dir else None,
        decisions_root=Path(args.decisions_dir) if args.decisions_dir else None,
        signals_root=Path(args.signals_dir) if args.signals_dir else None,
        distribution_root=Path(args.distribution_dir) if args.distribution_dir else None,
        production_root=Path(args.production_dir) if args.production_dir else None,
        analytics_root=Path(args.analytics_dir) if args.analytics_dir else None,
        dry_run=args.dry_run,
    )

    cmd = args.cmd or "summary"

    if cmd == "inspect":
        idx = load_index(roots["analytics_root"])
        print(json.dumps(idx.get("latest_snapshot") or (idx.get("snapshots") or [None])[-1], ensure_ascii=False, indent=2))
        return 0

    if cmd == "learning-inspect":
        lr = list_learnings(roots["analytics_root"]).get(args.learning_id)
        print(json.dumps(lr, ensure_ascii=False, indent=2))
        return 0 if lr else 1

    if cmd == "learn" or args.learn:
        if getattr(args, "list_only", False):
            print(json.dumps(list_learnings(roots["analytics_root"]), ensure_ascii=False, indent=2))
            return 0
        lres = generate_learning_records(
            opportunity_id=roots["opportunity_id"],
            opportunities_root=roots["opportunities_root"],
            experiments_root=roots["experiments_root"],
            decisions_root=roots["decisions_root"],
            distribution_root=roots["distribution_root"],
            analytics_root=roots["analytics_root"],
            dry_run=roots["dry_run"],
        )
        print(json.dumps({"ok": lres.ok, "learnings": lres.learnings, "errors": lres.errors}, ensure_ascii=False, indent=2))
        return 0 if lres.ok else 1

    ares = run_analytics(**{k: v for k, v in roots.items()})
    snap = ares.snapshot or {}
    if cmd == "funnel":
        print(json.dumps(snap.get("funnel"), ensure_ascii=False, indent=2))
    else:
        print(json.dumps({"ok": ares.ok, "snapshot": snap, "errors": ares.errors}, ensure_ascii=False, indent=2))
    return 0 if ares.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
