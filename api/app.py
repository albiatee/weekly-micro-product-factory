"""FastAPI app — local-only Factory read API + orchestrator dry-run."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from api.store_readers import list_products, project_root, read_index

app = FastAPI(
    title="Factory Backend API",
    version="0.1.0",
    description="Local-only Factory API: read stores, dry-run, knowledge search (P3/P4).",
)

# Local dashboard only — not an open internet API
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1",
        "http://127.0.0.1:8000",
        "http://localhost",
        "http://localhost:8000",
        "null",  # file:// dashboard
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# Optional root override for tests
_ROOT_OVERRIDE: Path | None = None


def get_root() -> Path:
    return _ROOT_OVERRIDE or project_root()


def set_root_override(path: Path | None) -> None:
    global _ROOT_OVERRIDE
    _ROOT_OVERRIDE = path


class DryRunRequest(BaseModel):
    stop_after: str = Field(default="DECIDE", description="Last orchestrator step")
    persist: bool = Field(default=False, description="Persist cycle record (default false in API)")


class DryRunResponse(BaseModel):
    ok: bool
    dry_run: bool = True
    live_forbidden: bool = True
    cycle: dict[str, Any] | None = None
    error: str | None = None


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "ok": True,
        "service": "factory-api",
        "version": "0.1.0",
        "mode": "local-only",
        "live_execution": False,
    }


def _get_collection(store: str, key: str) -> dict[str, Any]:
    return read_index(store, key, root=get_root())


@app.get("/signals")
def get_signals() -> dict[str, Any]:
    return _get_collection("signals", "signals")


@app.get("/opportunities")
def get_opportunities() -> dict[str, Any]:
    return _get_collection("opportunities", "opportunities")


@app.get("/experiments")
def get_experiments() -> dict[str, Any]:
    return _get_collection("experiments", "experiments")


@app.get("/decisions")
def get_decisions() -> dict[str, Any]:
    return _get_collection("decisions", "decisions")


@app.get("/production-specs")
def get_production_specs() -> dict[str, Any]:
    # production store may use production_specs or specs
    data = read_index("production", "production_specs", root=get_root())
    if data["count"] == 0 and data.get("store_status") == "ok":
        alt = read_index("production", "specs", root=get_root())
        if alt["count"]:
            return alt
    return data


@app.get("/distributions")
def get_distributions() -> dict[str, Any]:
    data = read_index("distribution", "plans", root=get_root())
    if data["count"] == 0:
        alt = read_index("distribution", "distributions", root=get_root())
        if alt["count"]:
            return alt
    return data


@app.get("/analytics/snapshots")
def get_analytics_snapshots() -> dict[str, Any]:
    """Legacy aggregate analytics snapshots (Phase 8-era store)."""
    data = read_index("analytics", "learnings", root=get_root())
    if data["count"] == 0:
        alt = read_index("analytics", "learning_records", root=get_root())
        if alt["count"]:
            return alt
    return data


@app.get("/cycles")
def get_cycles() -> dict[str, Any]:
    return _get_collection("cycles", "cycles")


@app.get("/products")
def get_products() -> dict[str, Any]:
    return list_products(root=get_root())


@app.post("/cycles/dry-run", response_model=DryRunResponse)
def post_cycles_dry_run(body: DryRunRequest | None = None) -> DryRunResponse:
    """Run orchestrator in dry-run only. Never live / build / publish."""
    body = body or DryRunRequest()
    # Hard reject any attempt to request live via query smuggling — body has no live flag
    try:
        from orchestrator.runner import run_cycle
    except Exception as e:
        return DryRunResponse(ok=False, error=f"orchestrator unavailable: {e}")

    root = get_root()
    try:
        cycle = run_cycle(
            dry_run=True,  # forced
            stop_after=body.stop_after or "DECIDE",
            signals_root=root / "data" / "signals",
            opportunities_root=root / "data" / "opportunities",
            experiments_root=root / "data" / "experiments",
            decisions_root=root / "data" / "decisions",
            cycles_root=root / "data" / "cycles",
            force_enabled=True,  # dry-run inspection only
            persist=bool(body.persist),
        )
    except Exception as e:
        return DryRunResponse(ok=False, error=str(e))

    if not cycle.get("dry_run", True):
        raise HTTPException(status_code=500, detail="dry_run invariant violated")

    return DryRunResponse(ok=True, dry_run=True, live_forbidden=True, cycle=cycle)




@app.get("/knowledge/search")
def knowledge_search(
    q: str = Query("", description="Idea or free-text query"),
    limit: int = Query(10, ge=0, le=50),
    min_score: float = Query(0.08, ge=0.0, le=1.0),
    types: str | None = Query(
        None,
        description="Comma-separated entity types: signal,opportunity,experiment,decision,learning,product",
    ),
) -> dict[str, Any]:
    """Advisory similarity search over real Factory history. Not a decision."""
    from knowledge.search import search as knowledge_search_fn

    entity_types = None
    if types:
        entity_types = [x.strip() for x in types.split(",") if x.strip()]
    return knowledge_search_fn(
        q,
        entity_types=entity_types,
        limit=limit,
        min_score=min_score,
        root=get_root(),
    )


@app.get("/knowledge/compare")
def knowledge_compare(
    q: str = Query(..., min_length=1, description="New idea text"),
    limit: int = Query(5, ge=0, le=20),
) -> dict[str, Any]:
    """Compare a new idea to historical matches — informational only."""
    from knowledge.search import compare_idea

    return compare_idea(q, limit=limit, root=get_root())



class ExperimentRunRequest(BaseModel):
    opportunity_id: str
    experiment_type: str = "smoke_page"
    metrics: dict[str, Any] | None = None
    dry_run: bool = False


@app.post("/experiments/run")
def experiments_run(body: ExperimentRunRequest) -> dict[str, Any]:
    """Limited experiment runner. Does not publish or bypass Policy."""
    from experiment.runner import run_experiment

    res = run_experiment(
        body.opportunity_id,
        experiment_type=body.experiment_type,
        metrics=body.metrics,
        dry_run=body.dry_run,
        opportunities_root=get_root() / "data" / "opportunities",
        experiments_root=get_root() / "data" / "experiments",
        runs_root=get_root() / "data" / "experiment_runs",
    )
    return {
        "ok": res.ok,
        "errors": res.errors,
        "notes": res.notes,
        "experiment": res.experiment,
        "run_dir": res.run_dir,
        "artifact_path": res.artifact_path,
        "metrics": res.metrics,
        "policy": res.policy,
        "live_publish": False,
    }


class ExperimentCompleteRequest(BaseModel):
    experiment_id: str
    metrics: dict[str, Any]


@app.post("/experiments/complete")
def experiments_complete(body: ExperimentCompleteRequest) -> dict[str, Any]:
    from experiment.runner import complete_with_metrics

    res = complete_with_metrics(
        body.experiment_id,
        body.metrics,
        opportunities_root=get_root() / "data" / "opportunities",
        experiments_root=get_root() / "data" / "experiments",
        runs_root=get_root() / "data" / "experiment_runs",
    )
    return {
        "ok": res.ok,
        "errors": res.errors,
        "experiment": res.experiment,
        "metrics": res.metrics,
        "policy": res.policy,
        "live_publish": False,
    }




class BuildRunRequest(BaseModel):
    decision_id: str
    dry_run: bool = False


@app.post("/builds/run")
def builds_run(body: BuildRunRequest) -> dict[str, Any]:
    """P6 automated build from execute Decision only. No public publish."""
    from production.automated_build import run_automated_build

    res = run_automated_build(
        body.decision_id,
        dry_run=body.dry_run,
        opportunities_root=get_root() / "data" / "opportunities",
        decisions_root=get_root() / "data" / "decisions",
        experiments_root=get_root() / "data" / "experiments",
        production_root=get_root() / "data" / "production",
        builds_root=get_root() / "data" / "builds",
    )
    return {
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
        "live_publish": False,
    }




@app.get("/analytics")
def get_analytics_list() -> dict[str, Any]:
    from analytics.records import list_analytics_records

    items = list_analytics_records(get_root() / "data" / "analytics")
    return {"items": items, "count": len(items), "store_status": "ok"}


@app.get("/analytics/{analytics_id}")
def get_analytics_by_id(analytics_id: str) -> dict[str, Any]:
    from analytics.records import get_analytics_record

    rec = get_analytics_record(analytics_id, get_root() / "data" / "analytics")
    if not rec:
        raise HTTPException(status_code=404, detail="analytics not found")
    return rec


@app.get("/learning")
def get_learning_list() -> dict[str, Any]:
    from learning.engine import list_learning_records

    items = list_learning_records(get_root() / "data" / "analytics")
    return {"items": items, "count": len(items), "store_status": "ok", "advisory": True}


@app.get("/learning/{learning_id}")
def get_learning_by_id(learning_id: str) -> dict[str, Any]:
    from learning.engine import list_learning_records

    items = list_learning_records(get_root() / "data" / "analytics")
    rec = items.get(learning_id)
    if not rec:
        raise HTTPException(status_code=404, detail="learning not found")
    return rec


class AnalyticsRecordRequest(BaseModel):
    metrics: dict[str, Any] | None = None
    build_id: str | None = None
    opportunity_id: str | None = None
    product_id: str | None = None
    period: str | None = "unspecified"
    not_available: bool = False
    generate_learning: bool = False


@app.post("/analytics/record")
def post_analytics_record(body: AnalyticsRecordRequest) -> dict[str, Any]:
    """Local-only: record user-supplied metrics. No publish / no decision change."""
    from analytics.records import record_analytics, record_not_available
    from learning.engine import generate_learning_from_analytics

    root = get_root() / "data" / "analytics"
    if body.not_available:
        res = record_not_available(
            build_id=body.build_id,
            opportunity_id=body.opportunity_id,
            product_id=body.product_id,
            analytics_root=root,
        )
    else:
        res = record_analytics(
            metrics=body.metrics or {},
            build_id=body.build_id,
            opportunity_id=body.opportunity_id,
            product_id=body.product_id,
            period=body.period,
            analytics_root=root,
        )
    out: dict[str, Any] = {
        "ok": res.ok,
        "errors": res.errors,
        "record": res.record,
        "live_publish": False,
        "decision_changed": False,
    }
    if res.ok and body.generate_learning and res.record:
        lr = generate_learning_from_analytics(res.record["id"], analytics_root=root)
        out["learning"] = lr.learning
        out["learning_ok"] = lr.ok
    return out




class CycleRunRequest(BaseModel):
    dry_run: bool = True
    opportunity_id: str | None = None
    metrics: dict[str, Any] | None = None
    force_enabled: bool = False


@app.post("/cycles/run")
def cycles_run(body: CycleRunRequest) -> dict[str, Any]:
    """P8 closed loop — local only. Default dry_run=True. No public publish."""
    from orchestrator.closed_loop import run_closed_loop

    res = run_closed_loop(
        dry_run=body.dry_run,
        opportunity_id=body.opportunity_id,
        metrics=body.metrics,
        force_enabled=body.force_enabled,
        persist=False if body.dry_run else True,
        signals_root=get_root() / "data" / "signals",
        opportunities_root=get_root() / "data" / "opportunities",
        experiments_root=get_root() / "data" / "experiments",
        decisions_root=get_root() / "data" / "decisions",
        production_root=get_root() / "data" / "production",
        builds_root=get_root() / "data" / "builds",
        analytics_root=get_root() / "data" / "analytics",
        cycles_root=get_root() / "data" / "cycles",
    )
    return {
        "ok": res.ok,
        "errors": res.errors,
        "cycle": res.cycle,
        "live_publish": False,
    }


@app.post("/cycles/live")
def post_cycles_live_forbidden() -> None:
    """Explicitly blocked — no live execution via API v0.1."""
    raise HTTPException(
        status_code=403,
        detail="Live cycle execution is forbidden in API v0.1. Use dry-run only.",
    )


@app.api_route("/cycles/execute", methods=["GET", "POST", "PUT"])
@app.api_route("/publish", methods=["GET", "POST", "PUT"])
@app.api_route("/build", methods=["GET", "POST", "PUT"])
def blocked_side_effects() -> None:
    raise HTTPException(status_code=403, detail="Side-effect endpoints are not available in API v0.1")
