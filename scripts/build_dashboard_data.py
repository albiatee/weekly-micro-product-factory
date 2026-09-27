#!/usr/bin/env python3
"""Build dashboard/data.json from real Factory stores (no fictional metrics)."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _load(path: Path, key: str) -> dict:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    raw = data.get(key)
    if isinstance(raw, dict):
        return raw
    # flat map of entities
    return {k: v for k, v in data.items() if k != "updated_at" and isinstance(v, dict)}


def _products() -> list[dict]:
    base = ROOT / "products" / "weekly"
    out: list[dict] = []
    if not base.exists():
        return out
    for week_dir in sorted(base.iterdir(), reverse=True):
        if not week_dir.is_dir():
            continue
        meta_path = week_dir / "meta.json"
        meta: dict = {}
        if meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
            except Exception:
                meta = {}
        out.append(
            {
                "week": meta.get("week") or week_dir.name,
                "title": meta.get("title") or week_dir.name,
                "description": meta.get("description") or "",
                "path": meta.get("path") or "",
                "build_method": meta.get("build_method") or "",
                "href": f"../products/weekly/{week_dir.name}/",
                "generated_at": meta.get("generated_at"),
                "diversity_score": meta.get("diversity_score"),
            }
        )
    return out


def main() -> int:
    signals = _load(ROOT / "data" / "signals" / "index.json", "signals")
    opps = _load(ROOT / "data" / "opportunities" / "index.json", "opportunities")
    exps = _load(ROOT / "data" / "experiments" / "index.json", "experiments")
    decisions = _load(ROOT / "data" / "decisions" / "index.json", "decisions")
    cycles = _load(ROOT / "data" / "cycles" / "index.json", "cycles")
    products = _products()

    qual = sum(1 for s in signals.values() if s.get("qualification_status") == "qualified")
    review = sum(1 for s in signals.values() if s.get("qualification_status") == "review")

    opp_list = []
    for oid, o in sorted(opps.items(), key=lambda x: x[0]):
        opp_list.append(
            {
                "id": oid,
                "title": (o.get("title") or "")[:120],
                "status": o.get("status"),
                "problem": (o.get("problem") or o.get("problem_statement") or "")[:200],
                "audience": o.get("audience") or o.get("target_user"),
                "signal_ids": o.get("signal_ids") or [],
                "solution_type": o.get("solution_type") or o.get("solution_direction"),
            }
        )

    exp_list = []
    for eid, e in sorted(exps.items(), key=lambda x: x[0]):
        exp_list.append(
            {
                "id": eid,
                "opportunity_id": e.get("opportunity_id"),
                "status": e.get("status"),
                "experiment_type": e.get("experiment_type"),
            }
        )

    cycle_list = []
    for cid, c in sorted(cycles.items(), key=lambda x: x[0], reverse=True):
        cycle_list.append(
            {
                "id": cid,
                "status": c.get("status"),
                "dry_run": c.get("dry_run"),
                "completed_steps": c.get("completed_steps") or [],
                "selection": c.get("selection") or {},
                "abort_reason": c.get("abort_reason"),
                "created_at": c.get("created_at"),
            }
        )

    signal_list = []
    for sid, s in list(sorted(signals.items(), key=lambda x: x[0]))[:50]:
        signal_list.append(
            {
                "id": sid,
                "qualification_status": s.get("qualification_status"),
                "intent_type": s.get("intent_type"),
                "evidence_strength": s.get("evidence_strength"),
                "source": s.get("source"),
                "problem_statement": (s.get("problem_statement") or "")[:160],
                "url": s.get("url"),
                "sector": (s.get("meta") or {}).get("sector"),
            }
        )

    payload = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "version": "p2.0.1",
        "overview": {
            "signals": len(signals),
            "signals_qualified": qual,
            "signals_review": review,
            "opportunities": len(opps),
            "experiments": len(exps),
            "decisions": len(decisions),
            "cycles": len(cycles),
            "products": len(products),
        },
        "signals": signal_list,
        "opportunities": opp_list,
        "experiments": exp_list,
        "cycles": cycle_list,
        "products": products,
        "actions": {
            "dry_run_cli": "python scripts/run_orchestrator_cycle.py --dry-run --stop-after SELECT",
            "rebuild_dashboard": "python scripts/build_dashboard_data.py",
            "new_idea": "GitHub Issues → قالب فكرة منتج جديد",
            "orchestrator_enabled_default": False,
        },
    }

    out_dir = ROOT / "dashboard"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "data.json"
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "path": str(out_path.relative_to(ROOT)), "overview": payload["overview"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
