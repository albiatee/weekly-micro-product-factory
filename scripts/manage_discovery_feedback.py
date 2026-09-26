#!/usr/bin/env python3
"""CLI: Phase 9 Discovery Feedback (human-gated)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from discovery_feedback.pipeline import (  # noqa: E402
    accept_hint,
    approve_hint,
    convert_to_signal,
    create_hint_from_learning,
    defer_hint,
    generate_feedback_from_learnings,
    reject_hint,
)
from discovery_feedback.store import list_hints  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description="Discovery Feedback (Phase 9)")
    p.add_argument("--learnings-dir", default=None)
    p.add_argument("--opportunities-dir", default=None)
    p.add_argument("--hints-dir", default=None)
    p.add_argument("--signals-dir", default=None)
    p.add_argument("--dry-run", action="store_true")
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("create")
    c.add_argument("--learning-id", required=True)
    c.add_argument("--created-by", default="system:discovery_feedback")
    c.add_argument("--feedback-type", default="other")

    sub.add_parser("generate", help="Generate candidate feedback from all learnings")

    for name in ("approve", "reject", "defer"):
        s = sub.add_parser(name)
        s.add_argument("--hint-id", required=True)
        s.add_argument("--reviewer", required=True, dest="reviewed_by")
        s.add_argument("--notes", default=None)

    conv = sub.add_parser("convert-to-signal")
    conv.add_argument("--hint-id", required=True)

    acc = sub.add_parser("accept", help="Legacy: approve + convert")
    acc.add_argument("--hint-id", required=True)
    acc.add_argument("--reviewer", default="human")

    ins = sub.add_parser("inspect")
    ins.add_argument("--hint-id", required=True)

    sub.add_parser("list")

    args = p.parse_args()
    lr = Path(args.learnings_dir) if args.learnings_dir else None
    opp = Path(args.opportunities_dir) if args.opportunities_dir else None
    hints = Path(args.hints_dir) if args.hints_dir else None
    sig = Path(args.signals_dir) if args.signals_dir else None

    if args.cmd == "list":
        print(json.dumps(list_hints(hints), ensure_ascii=False, indent=2))
        return 0
    if args.cmd == "inspect":
        print(json.dumps(list_hints(hints).get(args.hint_id), ensure_ascii=False, indent=2))
        return 0
    if args.cmd == "generate":
        results = generate_feedback_from_learnings(
            learnings_root=lr, opportunities_root=opp, hints_root=hints, dry_run=args.dry_run
        )
        print(json.dumps([{"ok": r.ok, "errors": r.errors, "hint": r.hint} for r in results], ensure_ascii=False, indent=2))
        return 0 if all(r.ok or "duplicate" in " ".join(r.errors) for r in results) else 1
    if args.cmd == "create":
        res = create_hint_from_learning(
            args.learning_id,
            learnings_root=lr,
            opportunities_root=opp,
            hints_root=hints,
            created_by=args.created_by,
            feedback_type=args.feedback_type,
            dry_run=args.dry_run,
        )
        print(json.dumps({"ok": res.ok, "errors": res.errors, "hint": res.hint}, ensure_ascii=False, indent=2))
        return 0 if res.ok else 1
    if args.cmd == "approve":
        res = approve_hint(args.hint_id, reviewed_by=args.reviewed_by, review_notes=args.notes, hints_root=hints, dry_run=args.dry_run)
    elif args.cmd == "reject":
        res = reject_hint(args.hint_id, reviewed_by=args.reviewed_by, review_notes=args.notes, hints_root=hints, dry_run=args.dry_run)
    elif args.cmd == "defer":
        res = defer_hint(args.hint_id, reviewed_by=args.reviewed_by, review_notes=args.notes, hints_root=hints, dry_run=args.dry_run)
    elif args.cmd == "convert-to-signal":
        res = convert_to_signal(args.hint_id, hints_root=hints, signals_root=sig, opportunities_root=opp, dry_run=args.dry_run)
    elif args.cmd == "accept":
        res = accept_hint(args.hint_id, hints_root=hints, signals_root=sig, opportunities_root=opp, reviewed_by=args.reviewer, dry_run=args.dry_run)
    else:
        return 1
    print(json.dumps({"ok": res.ok, "errors": res.errors, "hint": res.hint, "signal": res.signal}, ensure_ascii=False, indent=2))
    return 0 if res.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
