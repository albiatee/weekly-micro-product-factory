#!/usr/bin/env python3
"""CLI: Phase 9 Discovery Feedback (Learning → Hint → Human → Signal).

Does not create Opportunities or Decisions automatically.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from discovery_feedback.pipeline import (  # noqa: E402
    accept_hint,
    create_hint_from_learning,
    defer_hint,
    reject_hint,
)
from discovery_feedback.store import list_hints  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description="Manage discovery feedback hints")
    p.add_argument("--learnings-dir", default=None, help="analytics store dir (has learnings)")
    p.add_argument("--opportunities-dir", default=None)
    p.add_argument("--hints-dir", default=None)
    p.add_argument("--signals-dir", default=None)
    p.add_argument("--dry-run", action="store_true")
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("create")
    c.add_argument("--learning-id", required=True)
    c.add_argument("--created-by", default="system:discovery_feedback")

    for name in ("accept", "reject", "defer"):
        s = sub.add_parser(name)
        s.add_argument("--hint-id", required=True)

    sub.add_parser("list")

    args = p.parse_args()
    lr_root = Path(args.learnings_dir) if args.learnings_dir else None
    opp_root = Path(args.opportunities_dir) if args.opportunities_dir else None
    hints_root = Path(args.hints_dir) if args.hints_dir else None
    sig_root = Path(args.signals_dir) if args.signals_dir else None

    if args.cmd == "list":
        print(json.dumps(list_hints(hints_root), ensure_ascii=False, indent=2))
        return 0

    if args.cmd == "create":
        res = create_hint_from_learning(
            args.learning_id,
            learnings_root=lr_root,
            opportunities_root=opp_root,
            hints_root=hints_root,
            created_by=args.created_by,
            dry_run=args.dry_run,
        )
        print(json.dumps({"ok": res.ok, "errors": res.errors, "hint": res.hint}, ensure_ascii=False, indent=2))
        return 0 if res.ok else 1

    if args.cmd == "accept":
        res = accept_hint(
            args.hint_id,
            hints_root=hints_root,
            signals_root=sig_root,
            opportunities_root=opp_root,
            dry_run=args.dry_run,
        )
        print(
            json.dumps(
                {"ok": res.ok, "errors": res.errors, "hint": res.hint, "signal": res.signal},
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0 if res.ok else 1

    if args.cmd == "reject":
        res = reject_hint(args.hint_id, hints_root=hints_root, dry_run=args.dry_run)
    elif args.cmd == "defer":
        res = defer_hint(args.hint_id, hints_root=hints_root, dry_run=args.dry_run)
    else:
        return 1

    print(json.dumps({"ok": res.ok, "errors": res.errors, "hint": res.hint}, ensure_ascii=False, indent=2))
    return 0 if res.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
