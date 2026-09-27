"""P7 analytics records for builds/products — supplied metrics only."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .product_metrics import derive_metrics, validate_raw_metrics
from .store import load_index, save_index

DEFAULT_ROOT = Path(__file__).resolve().parents[1] / "data" / "analytics"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _analytics_id() -> str:
    return f"anl_{uuid.uuid4().hex[:16]}"


@dataclass
class RecordResult:
    ok: bool
    record: dict[str, Any] | None = None
    errors: list[str] = field(default_factory=list)


def list_analytics_records(root: Path | None = None) -> dict[str, dict[str, Any]]:
    data = load_index(root)
    raw = data.get("records")
    if isinstance(raw, dict):
        return {k: v for k, v in raw.items() if isinstance(v, dict)}
    return {}


def get_analytics_record(analytics_id: str, root: Path | None = None) -> dict[str, Any] | None:
    return list_analytics_records(root).get(analytics_id)


def upsert_analytics_record(record: dict[str, Any], root: Path | None = None) -> Path:
    data = load_index(root)
    data.setdefault("records", {})
    if not isinstance(data["records"], dict):
        data["records"] = {}
    rid = record.get("id")
    if not rid:
        raise ValueError("analytics record requires id")
    data["records"][rid] = record
    return save_index(data, root)


def record_analytics(
    *,
    metrics: dict[str, Any],
    build_id: str | None = None,
    opportunity_id: str | None = None,
    product_id: str | None = None,
    period: str | None = None,
    source: str = "user_supplied",
    notes: str | None = None,
    analytics_root: Path | None = None,
    require_at_least_one_metric: bool = True,
    dry_run: bool = False,
) -> RecordResult:
    """Create analytics record from supplied metrics. Never fabricates values."""
    errors: list[str] = []
    if not build_id and not product_id and not opportunity_id:
        errors.append("at least one of build_id, product_id, opportunity_id required")

    raw, m_errs = validate_raw_metrics(metrics)
    errors.extend(m_errs)
    if require_at_least_one_metric and not raw and not m_errs:
        errors.append("no metrics provided; refusing empty record (use status not_available path)")

    if errors:
        return RecordResult(False, errors=errors)

    status = "recorded" if raw else "not_available"
    derived = derive_metrics(raw)

    record = {
        "id": _analytics_id(),
        "build_id": build_id,
        "opportunity_id": opportunity_id,
        "product_id": product_id,
        "period": period or "unspecified",
        "metrics": {
            "raw": raw,
            "derived": derived,
        },
        "source": source,
        "source_note": "Metrics are user/system supplied — not invented market evidence.",
        "captured_at": _now(),
        "status": status,
        "notes": notes,
    }
    if not dry_run:
        upsert_analytics_record(record, analytics_root)
    return RecordResult(True, record=record)


def record_not_available(
    *,
    build_id: str | None = None,
    opportunity_id: str | None = None,
    product_id: str | None = None,
    reason: str = "no real metrics supplied",
    analytics_root: Path | None = None,
    dry_run: bool = False,
) -> RecordResult:
    if not build_id and not product_id and not opportunity_id:
        return RecordResult(False, errors=["identifier required"])
    record = {
        "id": _analytics_id(),
        "build_id": build_id,
        "opportunity_id": opportunity_id,
        "product_id": product_id,
        "period": "unspecified",
        "metrics": {"raw": {}, "derived": derive_metrics({})},
        "source": "none",
        "source_note": "No metrics available; values not fabricated.",
        "captured_at": _now(),
        "status": "not_available",
        "notes": reason,
    }
    if not dry_run:
        upsert_analytics_record(record, analytics_root)
    return RecordResult(True, record=record)
