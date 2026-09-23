#!/usr/bin/env python3
"""CLI: ingest manual Signals (Phase 2 Signal Discovery).

Usage:
  python scripts/ingest_signals.py path/to/signals.json
  python scripts/ingest_signals.py path/to/signals.jsonl --dry-run

Does not create Opportunities or touch weekly-build.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from discovery.pipeline import ingest_manual_file  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest manual market Signals")
    parser.add_argument("input", help="JSON or JSONL file of signal candidates")
    parser.add_argument(
        "--store-dir",
        default=None,
        help="Override data/signals directory",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and dedupe without writing storage",
    )
    args = parser.parse_args()

    store_root = Path(args.store_dir) if args.store_dir else None
    result = ingest_manual_file(args.input, store_root=store_root, dry_run=args.dry_run)

    summary = {
        "accepted": len(result.accepted),
        "rejected": len(result.rejected),
        "duplicates": len(result.duplicates),
        "dry_run": args.dry_run,
        "details": {
            "accepted_ids": [x["signal"]["id"] for x in result.accepted],
            "rejected": result.rejected,
            "duplicates": result.duplicates,
        },
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if result.rejected:
        return 1
    if result.duplicates and not result.accepted:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
