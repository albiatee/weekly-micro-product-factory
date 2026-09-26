#!/usr/bin/env python3
"""CLI: Phase 5 Decision Gate.

Create explicit Decisions from completed Experiment evidence.
Does NOT auto-execute from passed=true, scores, or thresholds.
Does NOT trigger production builds.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from decision.pipeline import create_decision  # noqa: E402
from decision.store import list_decisions  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description="Decision Gate for Opportunities")
    p.add_argument("--opportunities-dir", default=None)
    p.add_argument("--experiments-dir", default=None)
    p.add_argument("--signals-dir", default=None)
    p.add_argument("--decisions-dir", default=None)
    p.add_argument("--dry-run", action="store_true")
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("create")
    c.add_argument("--opportunity-id", required=True)
    c.add_argument("--verdict", required=True, choices=["execute", "iterate", "kill"])
    c.add_argument("--reason", required=True)
    c.add_argument(
        "--evidence-ref",
        action="append",
        dest="evidence_refs",
        default=[],
        help="exp_... or sig_... (repeatable)",
    )
    c.add_argument("--experiment-id", required=True)
    c.add_argument("--next-action", default=None)
    c.add_argument(
        "--decided-by",
        required=True,
        choices=["human", "human_with_agent_suggestion"],
    )
    c.add_argument("--agent-suggestion", default=None)

    sub.add_parser("list")
    ins = sub.add_parser("inspect")
    ins.add_argument("--decision-id", required=True)

    args = p.parse_args()
    opp_r = Path(args.opportunities_dir) if args.opportunities_dir else None
    exp_r = Path(args.experiments_dir) if args.experiments_dir else None
    sig_r = Path(args.signals_dir) if args.signals_dir else None
    dec_r = Path(args.decisions_dir) if args.decisions_dir else None

    if args.cmd == "list":
        print(json.dumps(list_decisions(dec_r), ensure_ascii=False, indent=2))
        return 0
    if args.cmd == "inspect":
        all_d = list_decisions(dec_r)
        print(json.dumps(all_d.get(args.decision_id), ensure_ascii=False, indent=2))
        return 0 if args.decision_id in all_d else 1

    if args.cmd == "create":
        refs = list(args.evidence_refs or [])
        if args.experiment_id and args.experiment_id not in refs:
            refs.append(args.experiment_id)
        res = create_decision(
            opportunity_id=args.opportunity_id,
            verdict=args.verdict,
            reason=args.reason,
            evidence_refs=refs,
            decided_by=args.decided_by,
            experiment_id=args.experiment_id,
            next_action=args.next_action,
            agent_suggestion=args.agent_suggestion,
            opportunities_root=opp_r,
            experiments_root=exp_r,
            signals_root=sig_r,
            decisions_root=dec_r,
            dry_run=args.dry_run,
        )
        print(
            json.dumps(
                {
                    "ok": res.ok,
                    "errors": res.errors,
                    "decision": res.decision,
                    "opportunity": res.opportunity,
                    "dry_run": args.dry_run,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0 if res.ok else 1

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
