"""Production Bridge: validated execute Decision → local digital artifact.

Uses existing templates/ under products/bridge/ without modifying weekly-build.yml.
"""
from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from decision.store import list_decisions
from opportunity.store import list_opportunities, upsert_opportunity

# Supported by current template-based production only
SUPPORTED_SOLUTION_TYPES = frozenset({"digital_micro"})

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TEMPLATES = REPO_ROOT / "templates"
DEFAULT_PRODUCTS = REPO_ROOT / "products" / "bridge"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _safe_segment(value: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9_-]+", "-", value.strip())[:64]
    return s.strip("-") or "item"


@dataclass
class BridgeResult:
    ok: bool
    opportunity: dict[str, Any] | None = None
    production_ref: dict[str, Any] | None = None
    errors: list[str] = field(default_factory=list)
    dry_run: bool = False


def _pick_template(templates_dir: Path, solution_type: str) -> Path | None:
    """Map solution type to an existing template folder with index.html."""
    if solution_type != "digital_micro":
        return None
    # Prefer calculator as default digital micro tool template
    for name in ("calculator", "landing-page", "weekly-tracker"):
        p = templates_dir / name
        if (p / "index.html").is_file():
            return p
    # any template
    if templates_dir.is_dir():
        for child in sorted(templates_dir.iterdir()):
            if child.is_dir() and (child / "index.html").is_file():
                return child
    return None


def _validate_gate(
    opportunity_id: str,
    *,
    opportunities: dict[str, dict[str, Any]],
    decisions: dict[str, dict[str, Any]],
) -> tuple[dict[str, Any] | None, dict[str, Any] | None, list[str]]:
    errors: list[str] = []
    opp = opportunities.get(opportunity_id)
    if not opp:
        return None, None, [f"opportunity not found: {opportunity_id}"]

    if opp.get("status") != "building":
        errors.append(
            f"opportunity status must be 'building' (got {opp.get('status')!r}); "
            f"Decision execute must have advanced status first"
        )

    if opp.get("production_ref"):
        errors.append(
            "opportunity already has production_ref; refusing duplicate production"
        )

    lid = opp.get("latest_decision_id")
    if not lid:
        errors.append("opportunity has no latest_decision_id")
        return opp, None, errors

    dec = decisions.get(lid)
    if not dec:
        errors.append(f"decision not found: {lid}")
        return opp, None, errors

    if dec.get("opportunity_id") != opportunity_id:
        errors.append(
            f"decision {lid} belongs to {dec.get('opportunity_id')!r}, not {opportunity_id!r}"
        )
    if dec.get("verdict") != "execute":
        errors.append(
            f"decision verdict must be 'execute' (got {dec.get('verdict')!r})"
        )

    st = opp.get("solution_type") or "unknown"
    if st not in SUPPORTED_SOLUTION_TYPES:
        errors.append(
            f"solution_type {st!r} is not supported by Production Bridge "
            f"(supported: {sorted(SUPPORTED_SOLUTION_TYPES)})"
        )

    return opp, dec, errors


def run_production_bridge(
    opportunity_id: str,
    *,
    opportunities_root: Path | None = None,
    decisions_root: Path | None = None,
    templates_dir: Path | None = None,
    products_dir: Path | None = None,
    repo_root: Path | None = None,
    dry_run: bool = False,
) -> BridgeResult:
    """Bridge Decision(execute)+Opportunity(building) → template artifact → shipped.

    Does not call weekly-build workflow. Does not update catalog/index.json.
    Unit tests should pass isolated roots so real products/catalog stay untouched.
    """
    templates_dir = templates_dir or DEFAULT_TEMPLATES
    products_dir = products_dir or DEFAULT_PRODUCTS

    opportunities = list_opportunities(opportunities_root)
    decisions = list_decisions(decisions_root)

    opp, dec, errors = _validate_gate(
        opportunity_id, opportunities=opportunities, decisions=decisions
    )
    if errors:
        return BridgeResult(False, opportunity=opp, errors=errors, dry_run=dry_run)

    assert opp is not None and dec is not None
    template = _pick_template(templates_dir, opp.get("solution_type") or "digital_micro")
    if not template:
        return BridgeResult(
            False,
            opportunity=opp,
            errors=["no usable template with index.html under templates/"],
            dry_run=dry_run,
        )

    seg = _safe_segment(opportunity_id)
    target = products_dir / seg
    rel_path = f"products/bridge/{seg}"

    production_ref = {
        "path": rel_path,
        "template": template.name,
        "decision_id": dec["id"],
        "opportunity_id": opportunity_id,
        "kind": "digital_micro_bridge",
        "built_at": _now(),
    }

    if dry_run:
        return BridgeResult(
            True,
            opportunity=opp,
            production_ref=production_ref,
            dry_run=True,
        )

    # Real write: copy template → products/bridge/<opp>/
    if target.exists():
        return BridgeResult(
            False,
            opportunity=opp,
            errors=[f"target already exists: {target}"],
            dry_run=False,
        )

    try:
        target.mkdir(parents=True, exist_ok=False)
        shutil.copy2(template / "index.html", target / "index.html")
        meta = {
            "title": opp.get("title") or template.name,
            "description": (opp.get("problem") or "")[:500],
            "opportunity_id": opportunity_id,
            "decision_id": dec["id"],
            "template": template.name,
            "solution_type": opp.get("solution_type"),
            "build_method": "production_bridge",
            "generated_at": _now(),
            "path": rel_path,
        }
        (target / "meta.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        # Verify artifact exists before shipped
        if not (target / "index.html").is_file():
            shutil.rmtree(target, ignore_errors=True)
            return BridgeResult(
                False,
                opportunity=opp,
                errors=["artifact missing after copy"],
            )
    except OSError as e:
        if target.exists():
            shutil.rmtree(target, ignore_errors=True)
        return BridgeResult(False, opportunity=opp, errors=[f"production failed: {e}"])

    # Success → shipped + production_ref
    opp_updated = {
        **opp,
        "status": "shipped",
        "production_ref": production_ref,
        "updated_at": _now(),
    }
    # building → shipped is allowed by OPP_TRANSITIONS
    from contracts.validate import validate_opportunity, validate_opportunity_transition

    tr = validate_opportunity_transition("building", "shipped")
    if not tr.ok:
        # leave artifact but do not claim shipped incorrectly
        return BridgeResult(
            False,
            opportunity=opp,
            production_ref=production_ref,
            errors=tr.errors + ["artifact may exist but status transition failed"],
        )
    vr = validate_opportunity(opp_updated)
    if not vr.ok:
        return BridgeResult(
            False,
            opportunity=opp_updated,
            production_ref=production_ref,
            errors=vr.errors,
        )

    upsert_opportunity(opp_updated, opportunities_root)
    return BridgeResult(
        True, opportunity=opp_updated, production_ref=production_ref, dry_run=False
    )
