#!/usr/bin/env python3
"""CLI: Phase 7 Distribution (manual-first).

Requires Opportunity status=shipped with production_ref.
Does not rebuild products or call external marketing APIs.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from distribution.pipeline import (  # noqa: E402
    cancel_plan,
    complete_plan,
    create_plan,
    pause_plan,
    record_action,
    record_result,
    start_plan,
)
from distribution.store import list_actions, list_plans  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description="Manage distribution plans")
    p.add_argument("--opportunities-dir", default=None)
    p.add_argument("--distribution-dir", default=None)
    p.add_argument("--products-dir", default=None)
    p.add_argument("--dry-run", action="store_true")
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("create")
    c.add_argument("--opportunity-id", required=True)
    c.add_argument("--channel", required=True)
    c.add_argument("--objective", required=True)
    c.add_argument("--audience", default=None)
    c.add_argument("--created-by", default="system:distribution")
    c.add_argument("--skip-artifact-check", action="store_true")

    for name in ("start", "pause", "complete", "cancel"):
        s = sub.add_parser(name)
        s.add_argument("--plan-id", required=True)

    a = sub.add_parser("record-action")
    a.add_argument("--plan-id", required=True)
    a.add_argument("--action-type", required=True)
    a.add_argument("--notes", default=None)

    r = sub.add_parser("record-result")
    r.add_argument("--plan-id", required=True)
    r.add_argument("--metrics-json", default=None)
    r.add_argument("--note", action="append", default=[])

    sub.add_parser("list")

    args = p.parse_args()
    opp_r = Path(args.opportunities_dir) if args.opportunities_dir else None
    dist_r = Path(args.distribution_dir) if args.distribution_dir else None
    prod_r = Path(args.products_dir) if args.products_dir else None

    if args.cmd == "list":
        print(
            json.dumps(
                {"plans": list_plans(dist_r), "actions": list_actions(dist_r)},
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    if args.cmd == "create":
        res = create_plan(
            args.opportunity_id,
            channel=args.channel,
            objective=args.objective,
            audience=args.audience,
            created_by=args.created_by,
            opportunities_root=opp_r,
            distribution_root=dist_r,
            products_root=prod_r,
            require_artifact=not args.skip_artifact_check,
            dry_run=args.dry_run,
        )
        print(json.dumps({"ok": res.ok, "errors": res.errors, "plan": res.plan}, ensure_ascii=False, indent=2))
        return 0 if res.ok else 1

    if args.cmd == "start":
        res = start_plan(args.plan_id, distribution_root=dist_r, dry_run=args.dry_run)
    elif args.cmd == "pause":
        res = pause_plan(args.plan_id, distribution_root=dist_r, dry_run=args.dry_run)
    elif args.cmd == "complete":
        res = complete_plan(args.plan_id, distribution_root=dist_r, dry_run=args.dry_run)
    elif args.cmd == "cancel":
        res = cancel_plan(args.plan_id, distribution_root=dist_r, dry_run=args.dry_run)
    elif args.cmd == "record-action":
        res = record_action(
            args.plan_id,
            action_type=args.action_type,
            notes=args.notes,
            distribution_root=dist_r,
            dry_run=args.dry_run,
        )
        print(
            json.dumps(
                {"ok": res.ok, "errors": res.errors, "plan": res.plan, "action": res.action},
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0 if res.ok else 1
    elif args.cmd == "record-result":
        metrics = json.loads(args.metrics_json) if args.metrics_json else None
        res = record_result(
            args.plan_id,
            metrics=metrics,
            qualitative_notes=args.note or None,
            distribution_root=dist_r,
            dry_run=args.dry_run,
        )
    else:
        return 1

    print(json.dumps({"ok": res.ok, "errors": res.errors, "plan": res.plan}, ensure_ascii=False, indent=2))
    return 0 if res.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
