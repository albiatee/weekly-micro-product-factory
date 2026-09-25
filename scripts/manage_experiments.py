#!/usr/bin/env python3
"""CLI: Phase 4 Validation Experiments.

Commands:
  create   — plan experiment for an opportunity
  start    — planned → running (syncs opportunity to experimenting)
  results  — record metrics / notes (no fabrication)
  complete — running → completed (requires results; NO Decision)
  abort    — planned|running → aborted (does NOT kill opportunity)
  list     — list experiments

Does not trigger production or create Decisions.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from experiment.pipeline import (  # noqa: E402
    abort_experiment,
    complete_experiment,
    create_experiment,
    record_results,
    start_experiment,
)
from experiment.store import list_experiments  # noqa: E402


def _print(obj: object) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2, default=str))


def main() -> int:
    p = argparse.ArgumentParser(description="Manage validation experiments")
    p.add_argument("--opportunities-dir", default=None)
    p.add_argument("--experiments-dir", default=None)
    p.add_argument("--dry-run", action="store_true")
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("create")
    c.add_argument("--opportunity-id", required=True)
    c.add_argument("--type", required=True, dest="experiment_type")
    c.add_argument("--hypothesis-test", default=None)
    c.add_argument("--measurement-plan", default=None, help="Text plan (required before start)")
    c.add_argument("--success-criteria", default=None, help="JSON object or text")
    c.add_argument("--failure-criteria", default=None, help="JSON object or text")
    c.add_argument("--target-population", default=None)
    c.add_argument("--duration", default=None)
    c.add_argument("--channel", default=None)
    c.add_argument("--created-by", default="system:experiment_engine")

    s = sub.add_parser("start")
    s.add_argument("--experiment-id", required=True)
    s.add_argument("--measurement-plan", default=None)

    r = sub.add_parser("results")
    r.add_argument("--experiment-id", required=True)
    r.add_argument("--metrics-json", default=None, help='e.g. \'{"signups": 3}\'')
    r.add_argument("--note", action="append", default=[])
    r.add_argument("--passed", choices=["true", "false", "null"], default="null")

    k = sub.add_parser("complete")
    k.add_argument("--experiment-id", required=True)

    a = sub.add_parser("abort")
    a.add_argument("--experiment-id", required=True)
    a.add_argument("--reason", default=None)

    sub.add_parser("list")
    ins = sub.add_parser("inspect")
    ins.add_argument("--experiment-id", required=True)

    args = p.parse_args()
    opp_root = Path(args.opportunities_dir) if args.opportunities_dir else None
    exp_root = Path(args.experiments_dir) if args.experiments_dir else None

    if args.cmd == "list":
        _print(list_experiments(exp_root))
        return 0
    if args.cmd == "inspect":
        from experiment.store import get_experiment
        _print(get_experiment(args.experiment_id, exp_root))
        return 0

    if args.cmd == "create":
        plan = args.measurement_plan
        import json as _json
        def _crit(v):
            if v is None:
                return None
            try:
                return _json.loads(v)
            except Exception:
                return v
        res = create_experiment(
            args.opportunity_id,
            experiment_type=args.experiment_type,
            hypothesis_test=args.hypothesis_test,
            measurement_plan=plan,
            success_criteria=_crit(args.success_criteria),
            failure_criteria=_crit(args.failure_criteria),
            target_population=args.target_population,
            duration=args.duration,
            channel=args.channel,
            created_by=args.created_by,
            opportunities_root=opp_root,
            experiments_root=exp_root,
            dry_run=args.dry_run,
        )
        _print({"ok": res.ok, "errors": res.errors, "experiment": res.experiment})
        return 0 if res.ok else 1

    if args.cmd == "start":
        res = start_experiment(
            args.experiment_id,
            measurement_plan=args.measurement_plan,
            opportunities_root=opp_root,
            experiments_root=exp_root,
            dry_run=args.dry_run,
        )
        _print(
            {
                "ok": res.ok,
                "errors": res.errors,
                "experiment": res.experiment,
                "opportunity": res.opportunity,
            }
        )
        return 0 if res.ok else 1

    if args.cmd == "results":
        metrics = json.loads(args.metrics_json) if args.metrics_json else None
        passed = None
        if args.passed == "true":
            passed = True
        elif args.passed == "false":
            passed = False
        res = record_results(
            args.experiment_id,
            metrics=metrics,
            qualitative_notes=args.note or None,
            passed=passed,
            experiments_root=exp_root,
            dry_run=args.dry_run,
        )
        _print({"ok": res.ok, "errors": res.errors, "experiment": res.experiment})
        return 0 if res.ok else 1

    if args.cmd == "complete":
        res = complete_experiment(
            args.experiment_id,
            experiments_root=exp_root,
            opportunities_root=opp_root,
            dry_run=args.dry_run,
        )
        _print({"ok": res.ok, "errors": res.errors, "experiment": res.experiment})
        return 0 if res.ok else 1

    if args.cmd == "abort":
        res = abort_experiment(
            args.experiment_id,
            reason=args.reason,
            experiments_root=exp_root,
            opportunities_root=opp_root,
            dry_run=args.dry_run,
        )
        _print({"ok": res.ok, "errors": res.errors, "experiment": res.experiment})
        return 0 if res.ok else 1

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
