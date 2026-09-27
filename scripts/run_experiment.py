#!/usr/bin/env python3
"""CLI for P5 Experiment Runner (limited, local)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from experiment.runner import complete_with_metrics, run_experiment  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description="P5 limited experiment runner")
    sub = p.add_subparsers(dest="cmd", required=True)

    run_p = sub.add_parser("run", help="Create+start experiment for opportunity")
    run_p.add_argument("--opportunity-id", required=True)
    run_p.add_argument("--type", default="smoke_page", dest="experiment_type")
    run_p.add_argument("--metrics-json", default=None, help='e.g. {"signups": 7}')
    run_p.add_argument("--metrics-file", type=Path, default=None)
    run_p.add_argument("--dry-run", action="store_true")

    fin = sub.add_parser("complete", help="Complete running experiment with metrics")
    fin.add_argument("--experiment-id", required=True)
    fin.add_argument("--metrics-json", required=True)

    args = p.parse_args()
    if args.cmd == "run":
        metrics = json.loads(args.metrics_json) if args.metrics_json else None
        res = run_experiment(
            args.opportunity_id,
            experiment_type=args.experiment_type,
            metrics=metrics,
            metrics_file=args.metrics_file,
            dry_run=args.dry_run,
        )
    else:
        metrics = json.loads(args.metrics_json)
        res = complete_with_metrics(args.experiment_id, metrics)

    out = {
        "ok": res.ok,
        "errors": res.errors,
        "notes": res.notes,
        "experiment_id": (res.experiment or {}).get("id"),
        "status": (res.experiment or {}).get("status"),
        "run_dir": res.run_dir,
        "artifact_path": res.artifact_path,
        "metrics": res.metrics,
        "policy": res.policy,
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if res.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
