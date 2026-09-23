#!/usr/bin/env python3
"""CLI: Phase 6 Production Bridge.

Only Decision(verdict=execute) + Opportunity(status=building) + digital_micro.
Does not rewrite weekly-build. Does not update catalog/index.json.
Does not implement Distribution.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from production.bridge import run_production_bridge  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description="Production Bridge from execute Decision")
    sub = p.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build", help="Build artifact for opportunity in building state")
    b.add_argument("--opportunity-id", required=True)
    b.add_argument("--opportunities-dir", default=None)
    b.add_argument("--decisions-dir", default=None)
    b.add_argument("--templates-dir", default=None)
    b.add_argument("--products-dir", default=None)
    b.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    if args.cmd == "build":
        res = run_production_bridge(
            args.opportunity_id,
            opportunities_root=Path(args.opportunities_dir) if args.opportunities_dir else None,
            decisions_root=Path(args.decisions_dir) if args.decisions_dir else None,
            templates_dir=Path(args.templates_dir) if args.templates_dir else None,
            products_dir=Path(args.products_dir) if args.products_dir else None,
            dry_run=args.dry_run,
        )
        print(
            json.dumps(
                {
                    "ok": res.ok,
                    "errors": res.errors,
                    "dry_run": res.dry_run,
                    "production_ref": res.production_ref,
                    "opportunity": res.opportunity,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0 if res.ok else 1
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
