#!/usr/bin/env python3
"""CLI: Phase 3 Opportunity Engine — Signals → hypothesized Opportunities.

Usage:
  python scripts/generate_opportunities.py
  python scripts/generate_opportunities.py --signal-id sig_abc --signal-id sig_def
  python scripts/generate_opportunities.py --combine --dry-run

Does not create Experiments/Decisions or touch weekly-build.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from opportunity.pipeline import generate_from_signal_ids, generate_from_store  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description="Generate hypothesized Opportunities from Signals")
    p.add_argument("--signal-id", action="append", dest="signal_ids", default=[])
    p.add_argument("--combine", action="store_true", help="One opportunity from all listed/all signals")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--signals-dir", default=None)
    p.add_argument("--opportunities-dir", default=None)
    p.add_argument("--created-by", default="system:opportunity_engine")
    args = p.parse_args()

    signals_root = Path(args.signals_dir) if args.signals_dir else None
    opp_root = Path(args.opportunities_dir) if args.opportunities_dir else None

    if args.signal_ids:
        result = generate_from_signal_ids(
            args.signal_ids,
            signals_root=signals_root,
            opportunities_root=opp_root,
            created_by=args.created_by,
            combine=args.combine,
            dry_run=args.dry_run,
        )
    else:
        result = generate_from_store(
            signals_root=signals_root,
            opportunities_root=opp_root,
            created_by=args.created_by,
            combine_all=args.combine,
            dry_run=args.dry_run,
        )

    out = {
        "accepted": len(result.accepted),
        "rejected": len(result.rejected),
        "duplicates": len(result.duplicates),
        "dry_run": args.dry_run,
        "opportunity_ids": [x["opportunity"]["id"] for x in result.accepted],
        "details": {
            "accepted": result.accepted,
            "rejected": result.rejected,
            "duplicates": result.duplicates,
        },
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    if result.rejected:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
