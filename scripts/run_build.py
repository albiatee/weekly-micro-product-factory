#!/usr/bin/env python3
"""CLI: P6 automated build from execute Decision."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from production.automated_build import run_automated_build  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description="P6 automated build (execute only)")
    p.add_argument("--decision-id", required=True)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    res = run_automated_build(args.decision_id, dry_run=args.dry_run)
    print(
        json.dumps(
            {
                "ok": res.ok,
                "build_id": res.build_id,
                "decision_id": res.decision_id,
                "opportunity_id": res.opportunity_id,
                "production_spec_id": res.production_spec_id,
                "artifact_path": res.artifact_path,
                "production_ref": res.production_ref,
                "errors": res.errors,
                "notes": res.notes,
                "dry_run": res.dry_run,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if res.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
