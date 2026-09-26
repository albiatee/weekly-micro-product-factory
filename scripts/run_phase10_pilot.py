#!/usr/bin/env python3
"""Phase 10 E2E pilot runner (isolated tmp dirs). SYSTEM VALIDATION only."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tests.test_e2e_phase10 import run_pilot  # noqa: E402


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="phase10_pilot_") as td:
        roots = {}
        base = Path(td)
        for n in ("sig", "opp", "exp", "dec", "prd", "dist", "an", "hints"):
            p = base / n
            p.mkdir()
            roots[n] = p
        try:
            chain = run_pilot(roots)
        except AssertionError as e:
            print("PHASE 10 E2E PILOT — FAIL")
            print(str(e))
            return 1
        print("PHASE 10 E2E PILOT")
        print(f"Signal: {chain['signal_id']}")
        print(f"Qualification: {chain['qualification']}")
        print(f"Opportunity: {chain['opportunity_id']}")
        print(f"Evidence ready: {chain['evidence_ready']}")
        print(f"Experiment: {chain['experiment_id']}")
        print(f"Experiment status: {chain['experiment_status']}")
        print(f"Decision: {chain['verdict']} ({chain['decision_id']})")
        print(f"Production Spec: {chain['production_spec_id']}")
        print(f"Distribution: {chain['distribution_id']} ({chain['distribution_status']})")
        print(f"Learning: {chain['learning_id']}")
        print(f"Discovery Feedback: approved ({chain['discovery_hint_id']})")
        print(f"Converted Signal: {chain['converted_signal_id']}")
        print()
        print(f"Traceability: {chain['traceability']}")
        print(f"Idempotency: {chain['idempotency']}")
        print(f"Human gate: {chain['human_gate']}")
        print()
        print("NOTE: Synthetic pilot fixtures only — NOT real market validation.")
        print(json.dumps(chain, indent=2))
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
