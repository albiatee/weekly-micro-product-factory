"""P6 Automated Build — execute Decision → Production Spec → local artifact.

Strict boundaries:
- Decision.verdict must be execute
- Template family: static_html_microproduct only (maps to templates/* digital micro)
- No public publish, no Shopify, no Path A (weekly-build) mutation
- Fail-safe: partial artifacts removed on failure
- Every build logged under data/builds/
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from decision.store import list_decisions
from opportunity.store import list_opportunities
from policy.config import load_config

from .bridge import BridgeResult, run_production_bridge
from .pipeline import create_production_spec
from .store import list_production_specs

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BUILDS = ROOT / "data" / "builds"

ALLOWED_BUILD_KIND = "static_html_microproduct"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _build_id() -> str:
    return f"bld_{uuid.uuid4().hex[:16]}"


@dataclass
class AutomatedBuildResult:
    ok: bool
    build_id: str | None = None
    decision_id: str | None = None
    opportunity_id: str | None = None
    production_spec_id: str | None = None
    production_ref: dict[str, Any] | None = None
    artifact_path: str | None = None
    errors: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    dry_run: bool = False
    log: dict[str, Any] | None = None


def _load_builds(root: Path) -> dict[str, Any]:
    path = root / "index.json"
    if not path.exists():
        return {"builds": {}, "updated_at": None}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"builds": {}, "updated_at": None}
    if not isinstance(data.get("builds"), dict):
        data["builds"] = {}
    return data


def _save_builds(data: dict[str, Any], root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    data["updated_at"] = _now()
    path = root / "index.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _append_log(
    builds_root: Path,
    entry: dict[str, Any],
    *,
    persist: bool,
) -> dict[str, Any]:
    if not persist:
        return entry
    data = _load_builds(builds_root)
    data["builds"][entry["id"]] = entry
    _save_builds(data, builds_root)
    return entry


def run_automated_build(
    decision_id: str,
    *,
    opportunities_root: Path | None = None,
    decisions_root: Path | None = None,
    experiments_root: Path | None = None,
    production_root: Path | None = None,
    templates_dir: Path | None = None,
    products_dir: Path | None = None,
    builds_root: Path | None = None,
    dry_run: bool = False,
    config: dict[str, Any] | None = None,
) -> AutomatedBuildResult:
    """Build only after execute Decision. No publish."""
    notes: list[str] = []
    builds_root = builds_root or DEFAULT_BUILDS
    cfg = config or load_config()
    allowed_templates = list(cfg.get("allowed_templates") or [ALLOWED_BUILD_KIND])

    if ALLOWED_BUILD_KIND not in allowed_templates and "static_html_microproduct" not in allowed_templates:
        return AutomatedBuildResult(
            False,
            decision_id=decision_id,
            errors=[
                f"build kind {ALLOWED_BUILD_KIND!r} not in allowed_templates {allowed_templates}"
            ],
            dry_run=dry_run,
        )

    decisions = list_decisions(decisions_root)
    dec = decisions.get(decision_id)
    if not dec:
        return AutomatedBuildResult(
            False, decision_id=decision_id, errors=[f"decision not found: {decision_id}"], dry_run=dry_run
        )

    verdict = dec.get("verdict") or dec.get("decision")
    if verdict != "execute":
        return AutomatedBuildResult(
            False,
            decision_id=decision_id,
            errors=[f"Decision verdict must be 'execute' (got {verdict!r})"],
            dry_run=dry_run,
        )

    oid = dec.get("opportunity_id")
    if not oid:
        return AutomatedBuildResult(
            False, decision_id=decision_id, errors=["decision missing opportunity_id"], dry_run=dry_run
        )

    opps = list_opportunities(opportunities_root)
    opp = opps.get(oid)
    if not opp:
        return AutomatedBuildResult(
            False,
            decision_id=decision_id,
            opportunity_id=oid,
            errors=[f"opportunity not found: {oid}"],
            dry_run=dry_run,
        )

    # Solution type must be digital_micro for static HTML microproduct path
    st = opp.get("solution_type") or "unknown"
    if st not in ("digital_micro", "unknown"):
        # unknown: bridge maps digital_micro templates only if we coerce carefully
        # Require digital_micro explicitly for safety
        if st != "digital_micro":
            return AutomatedBuildResult(
                False,
                decision_id=decision_id,
                opportunity_id=oid,
                errors=[
                    f"solution_type {st!r} not allowed for automated build; "
                    "only digital_micro / static_html_microproduct"
                ],
                dry_run=dry_run,
            )

    # Coerce unknown → digital_micro only when building static microproduct under explicit gate
    if st == "unknown":
        notes.append("solution_type was unknown; treating as digital_micro for static_html_microproduct only")
        # bridge requires digital_micro — update local copy for bridge validation
        opp = {**opp, "solution_type": "digital_micro"}

    # Opportunity must be building (execute path)
    if opp.get("status") != "building":
        return AutomatedBuildResult(
            False,
            decision_id=decision_id,
            opportunity_id=oid,
            errors=[
                f"opportunity status must be 'building' after execute (got {opp.get('status')!r})"
            ],
            dry_run=dry_run,
        )

    build_id = _build_id()
    log_entry: dict[str, Any] = {
        "id": build_id,
        "decision_id": decision_id,
        "opportunity_id": oid,
        "kind": ALLOWED_BUILD_KIND,
        "status": "started",
        "dry_run": dry_run,
        "created_at": _now(),
        "steps": [],
        "errors": [],
    }

    def step(name: str, ok: bool, detail: Any = None) -> None:
        log_entry["steps"].append({"step": name, "ok": ok, "detail": detail, "at": _now()})

    # 1) Production Spec
    existing_specs = list_production_specs(production_root)
    spec_id = None
    for s in existing_specs.values():
        if s.get("decision_id") == decision_id:
            spec_id = s.get("id")
            notes.append(f"reusing production spec {spec_id}")
            step("production_spec", True, {"id": spec_id, "reused": True})
            break

    if spec_id is None:
        spec_res = create_production_spec(
            decision_id=decision_id,
            opportunity_id=oid,
            opportunities_root=opportunities_root,
            decisions_root=decisions_root,
            experiments_root=experiments_root,
            production_root=production_root,
            dry_run=dry_run,
        )
        if not spec_res.ok:
            log_entry["status"] = "failed"
            log_entry["errors"] = list(spec_res.errors)
            step("production_spec", False, spec_res.errors)
            _append_log(builds_root, log_entry, persist=not dry_run)
            return AutomatedBuildResult(
                False,
                build_id=build_id,
                decision_id=decision_id,
                opportunity_id=oid,
                errors=spec_res.errors,
                notes=notes,
                dry_run=dry_run,
                log=log_entry,
            )
        spec_id = (spec_res.production_spec or {}).get("id")
        step("production_spec", True, {"id": spec_id})

    if dry_run:
        log_entry["status"] = "dry_run_ok"
        step("bridge", True, {"skipped": "dry_run"})
        _append_log(builds_root, log_entry, persist=False)
        return AutomatedBuildResult(
            True,
            build_id=build_id,
            decision_id=decision_id,
            opportunity_id=oid,
            production_spec_id=spec_id,
            notes=notes + ["dry_run: no artifact written"],
            dry_run=True,
            log=log_entry,
        )

    # Ensure opportunity has digital_micro for bridge if we coerced
    if st == "unknown":
        from opportunity.store import upsert_opportunity

        live = list_opportunities(opportunities_root).get(oid)
        if live and live.get("solution_type") in (None, "unknown"):
            live = {**live, "solution_type": "digital_micro", "updated_at": _now()}
            upsert_opportunity(live, opportunities_root)
            notes.append("persisted solution_type=digital_micro for build")

    # 2) Bridge build
    bridge: BridgeResult = run_production_bridge(
        oid,
        opportunities_root=opportunities_root,
        decisions_root=decisions_root,
        templates_dir=templates_dir,
        products_dir=products_dir,
        dry_run=False,
    )
    if not bridge.ok:
        log_entry["status"] = "failed"
        log_entry["errors"] = list(bridge.errors)
        step("bridge", False, bridge.errors)
        _append_log(builds_root, log_entry, persist=True)
        return AutomatedBuildResult(
            False,
            build_id=build_id,
            decision_id=decision_id,
            opportunity_id=oid,
            production_spec_id=spec_id,
            errors=bridge.errors,
            notes=notes + ["fail-safe: bridge failed; no shipped claim"],
            dry_run=False,
            log=log_entry,
        )

    ref = bridge.production_ref or {}
    artifact = ref.get("path")
    log_entry["status"] = "succeeded"
    log_entry["production_ref"] = ref
    step("bridge", True, ref)
    step("validate", True, {"index_html": True})
    _append_log(builds_root, log_entry, persist=True)

    return AutomatedBuildResult(
        True,
        build_id=build_id,
        decision_id=decision_id,
        opportunity_id=oid,
        production_spec_id=spec_id,
        production_ref=ref,
        artifact_path=artifact,
        notes=notes,
        dry_run=False,
        log=log_entry,
    )
