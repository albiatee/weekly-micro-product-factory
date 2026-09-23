"""Validators for Schema Contract v1 entities."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .constants import (
    DECIDED_BY,
    DECISION_VERDICTS,
    EVIDENCE_PREFIXES,
    EXPERIMENT_STATUSES,
    EXPERIMENT_TYPES,
    OPP_REQUIRES_SIGNALS,
    OPP_STATUSES,
    OPP_TRANSITIONS,
    PREFIX_DECISION,
    PREFIX_EXPERIMENT,
    PREFIX_LEARNING,
    PREFIX_OPPORTUNITY,
    PREFIX_SIGNAL,
    SIGNAL_SOURCES,
    SOLUTION_TYPES,
)


class ContractError(ValueError):
    """Raised when a contract rule is violated (optional strict mode)."""


@dataclass
class ValidationResult:
    ok: bool
    errors: list[str] = field(default_factory=list)

    def merge(self, other: "ValidationResult") -> "ValidationResult":
        return ValidationResult(ok=self.ok and other.ok, errors=self.errors + other.errors)


def _err(errors: list[str], msg: str) -> None:
    errors.append(msg)


def _require_str(obj: dict, key: str, errors: list[str], *, allow_empty: bool = False) -> None:
    if key not in obj:
        _err(errors, f"missing required field: {key}")
        return
    val = obj[key]
    if not isinstance(val, str):
        _err(errors, f"{key} must be a string")
        return
    if not allow_empty and not val.strip():
        _err(errors, f"{key} must be non-empty")


def _check_prefix(value: str, prefix: str, field_name: str, errors: list[str]) -> None:
    if not isinstance(value, str) or not value.startswith(prefix):
        _err(errors, f"{field_name} must start with '{prefix}'")


def validate_signal(obj: dict[str, Any]) -> ValidationResult:
    errors: list[str] = []
    if not isinstance(obj, dict):
        return ValidationResult(False, ["signal must be an object"])

    _require_str(obj, "id", errors)
    if "id" in obj and isinstance(obj["id"], str):
        _check_prefix(obj["id"], PREFIX_SIGNAL, "id", errors)

    _require_str(obj, "source", errors)
    if "source" in obj and isinstance(obj["source"], str):
        if obj["source"] not in SIGNAL_SOURCES:
            _err(
                errors,
                f"source must be one of reference list or 'other', got {obj['source']!r}",
            )

    _require_str(obj, "raw_text", errors)
    _require_str(obj, "captured_at", errors)

    # created_by optional
    if "created_by" in obj and obj["created_by"] is not None:
        if not isinstance(obj["created_by"], str) or not obj["created_by"].strip():
            _err(errors, "created_by must be a non-empty string when present")

    return ValidationResult(ok=len(errors) == 0, errors=errors)


def validate_opportunity(obj: dict[str, Any]) -> ValidationResult:
    errors: list[str] = []
    if not isinstance(obj, dict):
        return ValidationResult(False, ["opportunity must be an object"])

    _require_str(obj, "id", errors)
    if "id" in obj and isinstance(obj["id"], str):
        _check_prefix(obj["id"], PREFIX_OPPORTUNITY, "id", errors)

    _require_str(obj, "status", errors)
    status = obj.get("status")
    if isinstance(status, str) and status not in OPP_STATUSES:
        _err(errors, f"invalid status: {status!r}")

    for key in ("title", "problem", "audience", "created_by", "created_at", "updated_at"):
        _require_str(obj, key, errors)

    # signal_ids rules
    signal_ids = obj.get("signal_ids", [])
    if signal_ids is None:
        signal_ids = []
    if not isinstance(signal_ids, list):
        _err(errors, "signal_ids must be a list")
        signal_ids = []
    else:
        for i, sid in enumerate(signal_ids):
            if not isinstance(sid, str) or not sid.startswith(PREFIX_SIGNAL):
                _err(errors, f"signal_ids[{i}] must be a sig_... id")

    # draft: signal_ids optional; hypothesized and later (except killed-from-draft): required
    if isinstance(status, str):
        if status in (
            "hypothesized",
            "experimenting",
            "decided",
            "building",
            "shipped",
            "iterating",
        ):
            if not signal_ids:
                _err(
                    errors,
                    f"signal_ids must be non-empty when status is {status!r}",
                )
        # killed: empty allowed (draft→killed); non-empty also fine

    if "solution_type" in obj and obj["solution_type"] is not None:
        if obj["solution_type"] not in SOLUTION_TYPES:
            _err(errors, f"invalid solution_type: {obj['solution_type']!r}")

    # active_experiment_id required only when experimenting
    if isinstance(status, str) and status == "experimenting":
        ae = obj.get("active_experiment_id")
        if ae is None or (isinstance(ae, str) and not ae.strip()) or ae is False:
            _err(errors, "active_experiment_id is required when status is experimenting")
        elif not isinstance(ae, str) or not ae.startswith(PREFIX_EXPERIMENT):
            _err(errors, "active_experiment_id must be a valid exp_... identifier")
    elif "active_experiment_id" in obj and obj["active_experiment_id"]:
        if not str(obj["active_experiment_id"]).startswith(PREFIX_EXPERIMENT):
            _err(errors, "active_experiment_id must start with exp_")

    if "latest_decision_id" in obj and obj["latest_decision_id"]:
        if not str(obj["latest_decision_id"]).startswith(PREFIX_DECISION):
            _err(errors, "latest_decision_id must start with dec_")

    if isinstance(status, str) and status in (
        "decided",
        "building",
        "shipped",
        "iterating",
    ):
        lid = obj.get("latest_decision_id")
        if not lid:
            _err(
                errors,
                f"latest_decision_id is required when status is {status!r}",
            )

    return ValidationResult(ok=len(errors) == 0, errors=errors)


def validate_opportunity_transition(from_status: str, to_status: str) -> ValidationResult:
    errors: list[str] = []
    if from_status not in OPP_STATUSES:
        _err(errors, f"invalid from_status: {from_status!r}")
    if to_status not in OPP_STATUSES:
        _err(errors, f"invalid to_status: {to_status!r}")
    if errors:
        return ValidationResult(False, errors)

    allowed = OPP_TRANSITIONS.get(from_status, frozenset())
    if to_status not in allowed:
        _err(
            errors,
            f"illegal transition {from_status!r} → {to_status!r}; "
            f"allowed: {sorted(allowed) or 'none'}",
        )
    # Explicit guard: never hypothesized/experimenting → building
    if from_status in ("hypothesized", "experimenting") and to_status == "building":
        if not errors:  # may already have illegal transition
            _err(errors, "cannot jump to building without decided")

    return ValidationResult(ok=len(errors) == 0, errors=errors)


def validate_experiment(obj: dict[str, Any]) -> ValidationResult:
    errors: list[str] = []
    if not isinstance(obj, dict):
        return ValidationResult(False, ["experiment must be an object"])

    _require_str(obj, "id", errors)
    if "id" in obj and isinstance(obj["id"], str):
        _check_prefix(obj["id"], PREFIX_EXPERIMENT, "id", errors)

    _require_str(obj, "opportunity_id", errors)
    if "opportunity_id" in obj and isinstance(obj["opportunity_id"], str):
        _check_prefix(obj["opportunity_id"], PREFIX_OPPORTUNITY, "opportunity_id", errors)

    _require_str(obj, "status", errors)
    status = obj.get("status")
    if isinstance(status, str) and status not in EXPERIMENT_STATUSES:
        _err(errors, f"invalid experiment status: {status!r}")

    _require_str(obj, "experiment_type", errors)
    if "experiment_type" in obj and isinstance(obj["experiment_type"], str):
        if obj["experiment_type"] not in EXPERIMENT_TYPES:
            _err(errors, f"invalid experiment_type: {obj['experiment_type']!r}")

    _require_str(obj, "hypothesis_test", errors)
    _require_str(obj, "created_by", errors)
    _require_str(obj, "created_at", errors)
    _require_str(obj, "updated_at", errors)

    # measurement_plan required at running: non-empty string OR non-empty object
    if status == "running":
        plan = obj.get("measurement_plan")
        if isinstance(plan, str):
            if not plan.strip():
                _err(errors, "measurement_plan must be a non-empty string or non-empty object when status is running")
        elif isinstance(plan, dict):
            if len(plan) == 0:
                _err(errors, "measurement_plan must be a non-empty string or non-empty object when status is running")
        else:
            _err(
                errors,
                "measurement_plan is required when status is running "
                "(non-empty string or non-empty object)",
            )

    # success_threshold always optional — if present, basic shape check
    thr = obj.get("success_threshold")
    if thr is not None:
        if not isinstance(thr, dict):
            _err(errors, "success_threshold must be an object when present")

    return ValidationResult(ok=len(errors) == 0, errors=errors)


def validate_decision(obj: dict[str, Any]) -> ValidationResult:
    errors: list[str] = []
    if not isinstance(obj, dict):
        return ValidationResult(False, ["decision must be an object"])

    _require_str(obj, "id", errors)
    if "id" in obj and isinstance(obj["id"], str):
        _check_prefix(obj["id"], PREFIX_DECISION, "id", errors)

    _require_str(obj, "opportunity_id", errors)
    if "opportunity_id" in obj and isinstance(obj["opportunity_id"], str):
        _check_prefix(obj["opportunity_id"], PREFIX_OPPORTUNITY, "opportunity_id", errors)

    _require_str(obj, "verdict", errors)
    if "verdict" in obj and obj["verdict"] not in DECISION_VERDICTS:
        _err(errors, f"invalid verdict: {obj.get('verdict')!r}")

    _require_str(obj, "reason", errors)
    _require_str(obj, "decided_by", errors)
    if "decided_by" in obj and obj["decided_by"] not in DECIDED_BY:
        _err(errors, f"invalid decided_by: {obj.get('decided_by')!r}")
    _require_str(obj, "decided_at", errors)

    refs = obj.get("evidence_refs")
    if refs is None:
        _err(errors, "missing required field: evidence_refs")
        refs = []
    if not isinstance(refs, list):
        _err(errors, "evidence_refs must be a list")
        refs = []
    else:
        for i, ref in enumerate(refs):
            if not isinstance(ref, str):
                _err(errors, f"evidence_refs[{i}] must be a string")
                continue
            if not any(ref.startswith(p) for p in EVIDENCE_PREFIXES):
                _err(
                    errors,
                    f"evidence_refs[{i}] must start with exp_ or sig_ (contract v1), got {ref!r}",
                )

    # Strong recommendation: execute without evidence
    if obj.get("verdict") == "execute" and isinstance(refs, list) and len(refs) == 0:
        _err(
            errors,
            "execute without evidence_refs is not allowed unless documented exception; "
            "provide at least one exp_ or sig_ ref",
        )

    if "experiment_id" in obj and obj["experiment_id"]:
        if not str(obj["experiment_id"]).startswith(PREFIX_EXPERIMENT):
            _err(errors, "experiment_id must start with exp_")

    return ValidationResult(ok=len(errors) == 0, errors=errors)


def validate_learning_record(obj: dict[str, Any]) -> ValidationResult:
    errors: list[str] = []
    if not isinstance(obj, dict):
        return ValidationResult(False, ["learning_record must be an object"])

    _require_str(obj, "id", errors)
    if "id" in obj and isinstance(obj["id"], str):
        _check_prefix(obj["id"], PREFIX_LEARNING, "id", errors)

    _require_str(obj, "opportunity_id", errors)
    if "opportunity_id" in obj and isinstance(obj["opportunity_id"], str):
        _check_prefix(obj["opportunity_id"], PREFIX_OPPORTUNITY, "opportunity_id", errors)

    _require_str(obj, "what_worked", errors)
    _require_str(obj, "what_failed", errors)
    _require_str(obj, "created_at", errors)

    if "decision_id" in obj and obj["decision_id"]:
        if not str(obj["decision_id"]).startswith(PREFIX_DECISION):
            _err(errors, "decision_id must start with dec_")
    if "experiment_id" in obj and obj["experiment_id"]:
        if not str(obj["experiment_id"]).startswith(PREFIX_EXPERIMENT):
            _err(errors, "experiment_id must start with exp_")

    return ValidationResult(ok=len(errors) == 0, errors=errors)


def validate_graph(
    *,
    signals: dict[str, dict] | None = None,
    opportunities: dict[str, dict] | None = None,
    experiments: dict[str, dict] | None = None,
    decisions: dict[str, dict] | None = None,
    learnings: dict[str, dict] | None = None,
) -> ValidationResult:
    """Validate entities and that cross-references resolve."""
    signals = signals or {}
    opportunities = opportunities or {}
    experiments = experiments or {}
    decisions = decisions or {}
    learnings = learnings or {}

    result = ValidationResult(True, [])

    for sid, s in signals.items():
        r = validate_signal(s)
        if not r.ok:
            result.errors.extend(f"signal {sid}: {e}" for e in r.errors)
            result.ok = False
        if s.get("id") != sid:
            result.errors.append(f"signal key {sid} != id field")
            result.ok = False

    for oid, o in opportunities.items():
        r = validate_opportunity(o)
        if not r.ok:
            result.errors.extend(f"opportunity {oid}: {e}" for e in r.errors)
            result.ok = False
        for ref in o.get("signal_ids") or []:
            if ref not in signals:
                result.errors.append(f"opportunity {oid}: signal_ids ref {ref} not found")
                result.ok = False
        ae = o.get("active_experiment_id")
        if ae and ae not in experiments:
            result.errors.append(f"opportunity {oid}: active_experiment_id {ae} not found")
            result.ok = False
        ld = o.get("latest_decision_id")
        if ld and ld not in decisions:
            result.errors.append(f"opportunity {oid}: latest_decision_id {ld} not found")
            result.ok = False

    for eid, e in experiments.items():
        r = validate_experiment(e)
        if not r.ok:
            result.errors.extend(f"experiment {eid}: {e}" for e in r.errors)
            result.ok = False
        oid = e.get("opportunity_id")
        if oid and oid not in opportunities:
            result.errors.append(f"experiment {eid}: opportunity_id {oid} not found")
            result.ok = False

    for did, d in decisions.items():
        r = validate_decision(d)
        if not r.ok:
            result.errors.extend(f"decision {did}: {e}" for e in r.errors)
            result.ok = False
        oid = d.get("opportunity_id")
        if oid and oid not in opportunities:
            result.errors.append(f"decision {did}: opportunity_id {oid} not found")
            result.ok = False
        for ref in d.get("evidence_refs") or []:
            if ref.startswith(PREFIX_EXPERIMENT):
                if ref not in experiments:
                    result.errors.append(f"decision {did}: evidence ref {ref} not found")
                    result.ok = False
            elif ref.startswith(PREFIX_SIGNAL):
                if ref not in signals:
                    result.errors.append(f"decision {did}: evidence ref {ref} not found")
                    result.ok = False
        ex = d.get("experiment_id")
        if ex and ex not in experiments:
            result.errors.append(f"decision {did}: experiment_id {ex} not found")
            result.ok = False

    for lid, lr in learnings.items():
        r = validate_learning_record(lr)
        if not r.ok:
            result.errors.extend(f"learning {lid}: {e}" for e in r.errors)
            result.ok = False
        oid = lr.get("opportunity_id")
        if oid and oid not in opportunities:
            result.errors.append(f"learning {lid}: opportunity_id {oid} not found")
            result.ok = False

    return result
