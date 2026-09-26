"""Deterministic Policy evaluation — authorization only."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .risk import compute_risk


@dataclass
class PolicyResult:
    verdict: str  # execute | iterate | kill | no_decision
    rule_hits: list[str] = field(default_factory=list)
    reason: str = ""
    risk: float = 0.0

    @property
    def allows_produce(self) -> bool:
        return self.verdict == "execute"


def _criteria_met(criteria: Any, metrics: dict[str, Any] | None) -> bool | None:
    """Return True/False if evaluable, None if cannot determine."""
    if criteria is None or criteria == "":
        return None
    if metrics is None:
        return None
    # Structured threshold: {"metric": "signups", "op": ">=", "value": 10}
    if isinstance(criteria, dict):
        metric = criteria.get("metric")
        op = criteria.get("op", ">=")
        value = criteria.get("value")
        if metric is None or value is None:
            return None
        actual = (metrics or {}).get(metric)
        if actual is None:
            return None
        try:
            a, v = float(actual), float(value)
        except (TypeError, ValueError):
            return None
        if op == ">=":
            return a >= v
        if op == ">":
            return a > v
        if op == "<=":
            return a <= v
        if op == "<":
            return a < v
        if op == "==":
            return a == v
        return None
    # String criteria: not auto-evaluated as success — grey zone
    return None


def evaluate_decision(
    *,
    experiment: dict[str, Any] | None,
    opportunity: dict[str, Any] | None = None,
    metrics: dict[str, Any] | None = None,
    iteration_count: int = 0,
    config: dict[str, Any] | None = None,
    estimated_cost: float = 0.0,
    spend_so_far: float = 0.0,
    publish_channel: str = "github_pages",
    build_template: str = "static_html_microproduct",
) -> PolicyResult:
    cfg = config or {}
    hits: list[str] = []

    if not experiment:
        hits.append("no_experiment")
        return PolicyResult("no_decision", hits, "No experiment provided", 1.0)

    status = experiment.get("status")
    if status != "completed":
        hits.append("experiment_not_completed")
        return PolicyResult(
            "no_decision",
            hits,
            f"experiment.status is {status!r}; need completed",
            0.8,
        )

    metrics = metrics if metrics is not None else (experiment.get("results") or {}).get("metrics")
    if metrics is None and isinstance(experiment.get("results"), dict):
        metrics = experiment["results"].get("metrics")
    # also accept top-level metrics on results blob
    if metrics is None:
        res = experiment.get("results")
        if isinstance(res, dict) and any(
            k in res for k in ("signups", "metrics")
        ):
            metrics = res.get("metrics") if "metrics" in res else res

    measurement_invalid = metrics is None and not experiment.get("results")
    if measurement_invalid:
        hits.append("measurement_invalid")
        return PolicyResult("kill", hits, "No measurable results on completed experiment", 0.9)

    failure = experiment.get("failure_criteria")
    fail_met = _criteria_met(failure, metrics if isinstance(metrics, dict) else None)
    if fail_met is True:
        hits.append("failure_criteria_met")
        return PolicyResult("kill", hits, "Failure criteria met", 0.7)

    success = experiment.get("success_criteria")
    succ_met = _criteria_met(success, metrics if isinstance(metrics, dict) else None)

    criteria_snapshot_ok = success is not None or failure is not None
    snapshots_complete = bool(metrics is not None and criteria_snapshot_ok)

    allowed_channels = list(cfg.get("allowed_channels") or ["github_pages"])
    allowed_templates = list(cfg.get("allowed_templates") or ["static_html_microproduct"])
    max_risk = float(cfg.get("max_risk", 0.5))
    max_spend = float(cfg.get("max_spend_per_cycle", 0))
    remaining = max_spend - float(spend_so_far)
    budget_known = True  # explicit zero is known

    risk = compute_risk(
        experiment=experiment,
        channel=publish_channel,
        template=build_template,
        allowed_channels=allowed_channels,
        allowed_templates=allowed_templates,
        budget_known=budget_known,
        snapshots_complete=snapshots_complete,
    )

    max_iterations = int(cfg.get("max_iterations_per_opportunity", 2))

    if succ_met is True:
        hits.append("success_criteria_met")
        if risk > max_risk:
            hits.append("risk_exceeded")
            return PolicyResult("kill", hits, f"risk {risk:.2f} > max_risk {max_risk}", risk)
        if estimated_cost > remaining:
            hits.append("budget_exceeded")
            return PolicyResult("kill", hits, "estimated_cost exceeds remaining budget", risk)
        if publish_channel not in allowed_channels:
            hits.append("channel_not_allowed")
            return PolicyResult("kill", hits, f"channel {publish_channel!r} not allowed", risk)
        if build_template not in allowed_templates:
            hits.append("template_not_allowed")
            return PolicyResult("kill", hits, f"template {build_template!r} not allowed", risk)
        hits.append("execute_authorized")
        return PolicyResult("execute", hits, "Success criteria met and guardrail inputs OK", risk)

    # Grey zone or string-only criteria
    if iteration_count < max_iterations:
        hits.append("grey_zone_iterate")
        return PolicyResult(
            "iterate",
            hits,
            "Success/failure not deterministically met; iterate under cap",
            risk,
        )

    hits.append("grey_zone_kill")
    return PolicyResult("kill", hits, "Grey zone and iteration cap reached", risk)
