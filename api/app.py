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
    description="P3 local-only read API over weekly-micro-product-factory stores.",
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


@app.get("/learning")
def get_learning() -> dict[str, Any]:
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
