#!/usr/bin/env python3
"""CLI: Phase 6 Production Bridge.

- spec: create Production Specification from execute Decision (no deploy)
- build: optional digital_micro template artifact (existing path; does not update catalog)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from production.bridge import run_production_bridge  # noqa: E402
from production.pipeline import create_production_spec  # noqa: E402
from production.store import get_production_spec, list_production_specs  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description="Production Bridge / Production Specification")
    p.add_argument("--dry-run", action="store_true")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("spec", help="Create Production Specification from execute Decision")
    s.add_argument("--decision-id", default=None)
    s.add_argument("--opportunity-id", default=None)
    s.add_argument("--opportunities-dir", default=None)
    s.add_argument("--decisions-dir", default=None)
    s.add_argument("--experiments-dir", default=None)
    s.add_argument("--production-dir", default=None)

    b = sub.add_parser("build", help="Build digital_micro artifact for opportunity in building state")
    b.add_argument("--opportunity-id", required=True)
    b.add_argument("--opportunities-dir", default=None)
    b.add_argument("--decisions-dir", default=None)
    b.add_argument("--templates-dir", default=None)
    b.add_argument("--products-dir", default=None)

    sub.add_parser("list", help="List production specifications")
    ins = sub.add_parser("inspect")
    ins.add_argument("--production-id", required=True)
    ins.add_argument("--production-dir", default=None)

    args = p.parse_args()
    dry = getattr(args, "dry_run", False)

    if args.cmd == "list":
        root = Path(args.production_dir) if getattr(args, "production_dir", None) else None
        print(json.dumps(list_production_specs(root), ensure_ascii=False, indent=2))
        return 0

    if args.cmd == "inspect":
        root = Path(args.production_dir) if args.production_dir else None
        spec = get_production_spec(args.production_id, root)
        print(json.dumps(spec, ensure_ascii=False, indent=2))
        return 0 if spec else 1

    if args.cmd == "spec":
        res = create_production_spec(
            decision_id=args.decision_id,
            opportunity_id=args.opportunity_id,
            opportunities_root=Path(args.opportunities_dir) if args.opportunities_dir else None,
            decisions_root=Path(args.decisions_dir) if args.decisions_dir else None,
            experiments_root=Path(args.experiments_dir) if args.experiments_dir else None,
            production_root=Path(args.production_dir) if args.production_dir else None,
            dry_run=dry,
        )
        print(
            json.dumps(
                {"ok": res.ok, "errors": res.errors, "production_spec": res.production_spec},
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0 if res.ok else 1

    if args.cmd == "build":
        res = run_production_bridge(
            args.opportunity_id,
            opportunities_root=Path(args.opportunities_dir) if args.opportunities_dir else None,
            decisions_root=Path(args.decisions_dir) if args.decisions_dir else None,
            templates_dir=Path(args.templates_dir) if args.templates_dir else None,
            products_dir=Path(args.products_dir) if args.products_dir else None,
            dry_run=dry,
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
