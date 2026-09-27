"""P7 product/build metrics schema — no fabricated values."""
from __future__ import annotations

from typing import Any

# Canonical raw metric keys (v0.1)
RAW_METRIC_KEYS = frozenset(
    {
        "visits",
        "signups",
        "conversions",
        "revenue",
        "refunds",
        "active_users",
    }
)

# Derived metrics require valid inputs; never invent
DERIVED_KEYS = frozenset({"conversion_rate", "signup_rate", "refund_rate"})


def _is_nonneg_number(v: Any) -> bool:
    if v is None:
        return False
    if isinstance(v, bool):
        return False
    if isinstance(v, (int, float)):
        return v >= 0 and v == v  # not NaN
    return False


def validate_raw_metrics(metrics: dict[str, Any] | None) -> tuple[dict[str, Any], list[str]]:
    """Return cleaned raw metrics and errors. Unknown keys rejected."""
    errors: list[str] = []
    if metrics is None:
        return {}, ["metrics object required"]
    if not isinstance(metrics, dict):
        return {}, ["metrics must be an object"]

    cleaned: dict[str, Any] = {}
    for k, v in metrics.items():
        if k not in RAW_METRIC_KEYS:
            errors.append(f"unknown metric key: {k!r}")
            continue
        if v is None:
            # explicit null = not available; omit from cleaned
            continue
        if not _is_nonneg_number(v):
            errors.append(f"invalid value for {k}: must be non-negative number or null")
            continue
        cleaned[k] = float(v) if isinstance(v, float) else int(v) if isinstance(v, int) else v
        # normalize floats that are whole
        if isinstance(cleaned[k], float) and cleaned[k].is_integer():
            cleaned[k] = int(cleaned[k])
    return cleaned, errors


def derive_metrics(raw: dict[str, Any]) -> dict[str, Any | None]:
    """Compute derived metrics only when inputs are valid. No division by zero."""
    out: dict[str, Any | None] = {
        "conversion_rate": None,
        "signup_rate": None,
        "refund_rate": None,
    }

    visits = raw.get("visits")
    signups = raw.get("signups")
    conversions = raw.get("conversions")
    revenue = raw.get("revenue")
    refunds = raw.get("refunds")

    if _is_nonneg_number(visits) and visits > 0 and _is_nonneg_number(signups):
        out["signup_rate"] = round(float(signups) / float(visits), 6)
    if _is_nonneg_number(visits) and visits > 0 and _is_nonneg_number(conversions):
        out["conversion_rate"] = round(float(conversions) / float(visits), 6)
    elif _is_nonneg_number(signups) and signups > 0 and _is_nonneg_number(conversions):
        # fallback denominator only if visits missing
        out["conversion_rate"] = round(float(conversions) / float(signups), 6)

    if _is_nonneg_number(revenue) and revenue > 0 and _is_nonneg_number(refunds):
        out["refund_rate"] = round(float(refunds) / float(revenue), 6)

    return out
