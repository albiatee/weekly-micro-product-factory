#!/usr/bin/env python3
"""Record user-supplied product metrics (P7). Never invents market evidence."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from analytics.records import record_analytics, record_not_available  # noqa: E402
from learning.engine import generate_learning_from_analytics  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description="P7 record analytics + optional learning")
    p.add_argument("--build-id")
    p.add_argument("--opportunity-id")
    p.add_argument("--product-id")
    p.add_argument("--period", default="unspecified")
    p.add_argument("--metrics-json", help='e.g. {"visits":100,"signups":10}')
    p.add_argument("--not-available", action="store_true")
    p.add_argument("--generate-learning", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    if args.not_available:
        res = record_not_available(
            build_id=args.build_id,
            opportunity_id=args.opportunity_id,
            product_id=args.product_id,
            dry_run=args.dry_run,
        )
    else:
        if not args.metrics_json:
            print(json.dumps({"ok": False, "errors": ["--metrics-json or --not-available required"]}))
            return 1
        metrics = json.loads(args.metrics_json)
        res = record_analytics(
            metrics=metrics,
            build_id=args.build_id,
            opportunity_id=args.opportunity_id,
            product_id=args.product_id,
            period=args.period,
            dry_run=args.dry_run,
        )

    out: dict = {"ok": res.ok, "errors": res.errors, "record": res.record}
    if res.ok and args.generate_learning and res.record:
        lr = generate_learning_from_analytics(
            res.record["id"], dry_run=args.dry_run
        )
        out["learning"] = lr.learning
        out["learning_ok"] = lr.ok
        out["learning_errors"] = lr.errors

    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if res.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
