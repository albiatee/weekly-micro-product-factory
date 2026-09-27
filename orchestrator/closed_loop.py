"""P8 Closed Autonomous Loop — sequences P0–P7 under Policy/Guardrails/Kill Switch.

LLM is never the decision authority. No public publish.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from policy.config import load_config
from policy.evaluate import evaluate_decision
from policy.select import select_opportunities
from discovery.quality import apply_quality, is_opportunity_eligible
from discovery.store import list_signals
from opportunity.pipeline import generate_from_signal_ids
from opportunity.store import list_opportunities, upsert_opportunity
from opportunity.evidence import is_evidence_ready
from experiment.runner import run_experiment, complete_with_metrics
from experiment.store import list_experiments, get_experiment
from decision.pipeline import create_decision
from decision.store import list_decisions
from production.automated_build import run_automated_build
from analytics.records import record_analytics, record_not_available
from learning.engine import generate_learning_from_analytics
from guardrails.checks import check_produce_path

from .cycle import new_cycle_record, new_cycle_id
from .kill_switch import is_enabled
from .state_machine import transition
from .store import upsert_cycle, get_cycle

ROOT = Path(__file__).resolve().parents[1]


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class LoopResult:
    ok: bool
    cycle: dict[str, Any]
    errors: list[str] = field(default_factory=list)


def _set_state(cycle: dict[str, Any], new_state: str) -> None:
    ok, msg = transition(cycle.get("state") or "created", new_state)
    if not ok:
        raise RuntimeError(msg)
    cycle["state"] = new_state
    cycle["updated_at"] = _now()


def _fail(cycle: dict[str, Any], stage: str, reason: str) -> dict[str, Any]:
    cycle["status"] = "failed"
    try:
        _set_state(cycle, "failed")
    except RuntimeError:
        cycle["state"] = "failed"
    cycle["failure_stage"] = stage
    cycle["failure_reason"] = reason
    cycle["abort_reason"] = reason
    cycle["completed_at"] = _now()
    return cycle


def run_closed_loop(
    *,
    dry_run: bool = True,
    metrics: dict[str, Any] | None = None,
    signal_ids: list[str] | None = None,
    opportunity_id: str | None = None,
    cycle_id: str | None = None,
    force_enabled: bool = False,
    persist: bool = True,
    config_path: Path | None = None,
    signals_root: Path | None = None,
    opportunities_root: Path | None = None,
    experiments_root: Path | None = None,
    decisions_root: Path | None = None,
    production_root: Path | None = None,
    builds_root: Path | None = None,
    analytics_root: Path | None = None,
    cycles_root: Path | None = None,
    templates_dir: Path | None = None,
    products_dir: Path | None = None,
    experiment_runs_root: Path | None = None,
) -> LoopResult:
    """Run one closed factory cycle. Default dry_run=True for safety."""
    config = load_config(config_path)
    errors: list[str] = []

    # Idempotency: same cycle_id already terminal → return stored record, no side effects
    if cycle_id:
        existing = get_cycle(cycle_id, cycles_root)
        if existing and existing.get("status") in ("completed", "failed", "killed", "aborted"):
            existing = dict(existing)
            existing["idempotent_replay"] = True
            existing["live_publish"] = False
            return LoopResult(
                existing.get("status") == "completed" and existing.get("outcome") not in (None, ""),
                existing,
                errors=list(existing.get("errors") or []),
            )
        if existing and existing.get("status") == "running":
            return LoopResult(
                False,
                existing,
                errors=[f"cycle {cycle_id} still running; refusing concurrent re-entry"],
            )

    cycle = new_cycle_record(
        policy_id=config.get("policy_id", "policy_autonomous_factory_v0"),
        policy_version=config.get("policy_version", "0.1.0"),
        dry_run=dry_run,
    )
    if cycle_id:
        cycle["id"] = cycle_id
    cycle["state"] = "created"
    cycle["loop_version"] = "p8.0.1"
    cycle["live_publish"] = False
    cycle.setdefault("signal_ids", [])
    cycle.setdefault("opportunity_ids", [])
    cycle.setdefault("experiment_ids", [])
    cycle.setdefault("decision_ids", [])
    cycle.setdefault("build_ids", [])
    cycle.setdefault("analytics_ids", [])
    cycle.setdefault("learning_ids", [])
    cycle["outcome"] = None

    def log(step: str, ok: bool, **payload: Any) -> None:
        cycle.setdefault("step_log", []).append({"step": step, "ok": ok, "at": _now(), **payload})
        if ok and step not in cycle.get("completed_steps", []):
            cycle.setdefault("completed_steps", []).append(step)

    # --- Kill switch ---
    if not dry_run and not force_enabled and not is_enabled(config):
        cycle["status"] = "killed"
        cycle["state"] = "killed"
        cycle["failure_stage"] = "kill_switch"
        cycle["failure_reason"] = "ORCHESTRATOR_ENABLED is false / kill switch closed"
        cycle["abort_reason"] = cycle["failure_reason"]
        cycle["completed_at"] = _now()
        log("KILL_SWITCH", False, reason=cycle["failure_reason"])
        if persist:
            upsert_cycle(cycle, cycles_root)
        return LoopResult(False, cycle, errors=[cycle["failure_reason"]])

    try:
        # DISCOVER / QUALIFY
        _set_state(cycle, "discovering")
        signals = list_signals(signals_root)
        qualified: list[str] = []
        if signal_ids:
            qualified = [s for s in signal_ids if s in signals]
        else:
            for sid, sig in signals.items():
                s2 = apply_quality(dict(sig))
                if is_opportunity_eligible(s2):
                    qualified.append(sid)
        cycle["signal_ids"] = qualified
        log("QUALIFY", True, count=len(qualified))
        if not qualified and not opportunity_id:
            return LoopResult(
                False,
                _fail(cycle, "discovering", "no qualified signals and no opportunity_id"),
                ["no qualified signals"],
            )

        # OPPORTUNITY
        _set_state(cycle, "opportunity")
        opps = list_opportunities(opportunities_root)
        selected_oid = opportunity_id
        if selected_oid is None:
            # generate if needed (skip write on dry_run)
            if not dry_run and qualified:
                existing_for = {
                    oid
                    for oid, o in opps.items()
                    for sid in (o.get("signal_ids") or [])
                    if sid in qualified
                }
                if not existing_for:
                    generate_from_signal_ids(
                        qualified[:3],
                        signals_root=signals_root,
                        opportunities_root=opportunities_root,
                        created_by="orchestrator:closed_loop",
                        combine=False,
                    )
                    opps = list_opportunities(opportunities_root)
            # select_opportunities expects a list of opportunity dicts
            ranked = select_opportunities(list(opps.values()), config=config)
            if ranked:
                selected_oid = ranked[0].get("id")
            else:
                for oid, o in opps.items():
                    if is_evidence_ready(o)[0]:
                        selected_oid = oid
                        break
        if not selected_oid or selected_oid not in list_opportunities(opportunities_root):
            return LoopResult(
                False,
                _fail(cycle, "opportunity", f"no eligible opportunity ({selected_oid})"),
                ["no opportunity"],
            )
        cycle["opportunity_ids"] = [selected_oid]
        opp = list_opportunities(opportunities_root)[selected_oid]
        log("OPPORTUNITY", True, opportunity_id=selected_oid)

        # EXPERIMENT (required by default)
        _set_state(cycle, "experimenting")
        exp_id = None
        # reuse completed experiment on opportunity if present
        for eid, e in list_experiments(experiments_root).items():
            if e.get("opportunity_id") == selected_oid and e.get("status") == "completed":
                exp_id = eid
                break
        if exp_id is None:
            if dry_run:
                log("EXPERIMENT", True, dry_run=True, note="would_create_and_run_experiment")
                cycle.setdefault("refs", {})["experiment_dry_run"] = True
            else:
                er = run_experiment(
                    selected_oid,
                    experiment_type="smoke_page",
                    metrics=metrics,
                    success_criteria={"metric": "signups", "op": ">=", "value": 5},
                    failure_criteria={"metric": "signups", "op": "<", "value": 1},
                    opportunities_root=opportunities_root,
                    experiments_root=experiments_root,
                    runs_root=experiment_runs_root,
                    evaluate_policy=False,
                    dry_run=False,
                )
                if not er.ok or not er.experiment:
                    return LoopResult(
                        False,
                        _fail(cycle, "experimenting", "; ".join(er.errors) or "experiment failed"),
                        er.errors,
                    )
                exp = er.experiment
                exp_id = exp["id"]
                if exp.get("status") == "running" and metrics:
                    done = complete_with_metrics(
                        exp_id,
                        metrics,
                        opportunities_root=opportunities_root,
                        experiments_root=experiments_root,
                        runs_root=experiment_runs_root,
                        evaluate_policy=False,
                    )
                    if not done.ok:
                        return LoopResult(
                            False,
                            _fail(cycle, "experimenting", "; ".join(done.errors)),
                            done.errors,
                        )
                    exp = done.experiment or exp
                    exp_id = exp["id"]
                if exp.get("status") != "completed":
                    # leave running — cannot decide/build
                    cycle["experiment_ids"] = [exp_id]
                    log("EXPERIMENT", True, status=exp.get("status"), note="awaiting_metrics")
                    cycle["status"] = "completed"
                    cycle["outcome"] = "experiment_pending_metrics"
                    _set_state(cycle, "completed")
                    cycle["completed_at"] = _now()
                    if persist:
                        upsert_cycle(cycle, cycles_root)
                    cycle["notes"] = ["experiment_pending_metrics"]
                    return LoopResult(True, cycle)
        cycle["experiment_ids"] = [exp_id] if exp_id else []
        exp = get_experiment(exp_id, experiments_root) if exp_id else None
        log("EXPERIMENT", True, experiment_id=exp_id, status=(exp or {}).get("status"))

        if not exp or exp.get("status") != "completed":
            if dry_run:
                log("EXPERIMENT", True, dry_run_placeholder=True)
            else:
                return LoopResult(
                    False,
                    _fail(cycle, "experimenting", "experiment not completed"),
                    ["experiment required"],
                )

        # DECIDE
        _set_state(cycle, "deciding")
        exp_metrics = metrics or ((exp or {}).get("results") or {}).get("metrics") or {}
        policy = evaluate_decision(
            experiment=exp,
            opportunity=opp,
            metrics=exp_metrics if isinstance(exp_metrics, dict) else None,
            config=config,
            estimated_cost=0.0,
            build_template="static_html_microproduct",
            publish_channel="github_pages",
        )
        cycle.setdefault("refs", {})["policy_verdict"] = policy.verdict
        cycle["refs"]["policy_reason"] = policy.reason
        cycle["refs"]["rule_hits"] = policy.rule_hits
        log("DECIDE", True, verdict=policy.verdict, reason=policy.reason)

        decision_id = None
        if not dry_run and exp and policy.verdict in ("execute", "iterate", "kill"):
            reason = (policy.reason or "").strip()
            if len(reason) < 20:
                reason = (
                    f"Policy verdict={policy.verdict} based on completed experiment "
                    f"{exp['id']} and rule_hits={policy.rule_hits}."
                )
            dres = create_decision(
                opportunity_id=selected_oid,
                experiment_id=exp["id"],
                verdict=policy.verdict,
                reason=reason,
                evidence_refs=[exp["id"]],
                decided_by="policy:policy_autonomous_factory_v0",
                opportunities_root=opportunities_root,
                experiments_root=experiments_root,
                decisions_root=decisions_root,
            )
            if dres.ok and dres.decision:
                decision_id = dres.decision["id"]
                cycle["decision_ids"] = [decision_id]
            else:
                return LoopResult(
                    False,
                    _fail(cycle, "deciding", "; ".join(dres.errors)),
                    dres.errors,
                )
        elif dry_run:
            log("DECIDE", True, dry_run=True, would_verdict=policy.verdict)

        # Non-execute paths end without build
        if policy.verdict != "execute":
            cycle["status"] = "completed"
            cycle["outcome"] = f"decision_{policy.verdict}"
            # optional learning path still allowed
            _set_state(cycle, "learning")
            log("SKIP_BUILD", True, reason=f"verdict={policy.verdict}")
            _set_state(cycle, "completed")
            cycle["completed_at"] = _now()
            if persist:
                upsert_cycle(cycle, cycles_root)
            return LoopResult(True, cycle)

        # BUILD gate
        gr = check_produce_path(
            verdict="execute",
            dry_run=dry_run,
            criteria_snapshot=True,
            metrics_snapshot=exp_metrics if isinstance(exp_metrics, dict) else {},
            build_template="static_html_microproduct",
            config=config,
        )
        if not gr.ok:
            return LoopResult(
                False,
                _fail(cycle, "deciding", "; ".join(gr.errors)),
                gr.errors,
            )

        if dry_run:
            log("BUILD", True, dry_run=True, note="would_call_P6_automated_build")
            cycle["status"] = "completed"
            cycle["outcome"] = "dry_run_execute_would_build"
            _set_state(cycle, "completed")
            cycle["completed_at"] = _now()
            if persist:
                upsert_cycle(cycle, cycles_root)
            return LoopResult(True, cycle)

        # Ensure opportunity is building after execute decision
        opp2 = list_opportunities(opportunities_root).get(selected_oid)
        if not opp2 or opp2.get("status") != "building":
            return LoopResult(
                False,
                _fail(cycle, "building", f"opportunity status not building ({(opp2 or {}).get('status')})"),
                ["invalid opportunity status"],
            )

        if not decision_id:
            return LoopResult(
                False,
                _fail(cycle, "building", "missing decision"),
                ["missing decision"],
            )

        _set_state(cycle, "building")
        bres = run_automated_build(
            decision_id,
            opportunities_root=opportunities_root,
            decisions_root=decisions_root,
            experiments_root=experiments_root,
            production_root=production_root,
            builds_root=builds_root,
            templates_dir=templates_dir,
            products_dir=products_dir,
            dry_run=False,
            config=config,
        )
        if not bres.ok:
            return LoopResult(
                False,
                _fail(cycle, "building", "; ".join(bres.errors)),
                bres.errors,
            )
        if bres.build_id:
            cycle["build_ids"] = [bres.build_id]
        log("BUILD", True, build_id=bres.build_id, artifact=bres.artifact_path)

        # MEASURE
        _set_state(cycle, "measuring")
        if metrics:
            ares = record_analytics(
                metrics=metrics,
                build_id=bres.build_id,
                opportunity_id=selected_oid,
                analytics_root=analytics_root,
            )
        else:
            ares = record_not_available(
                build_id=bres.build_id,
                opportunity_id=selected_oid,
                reason="no metrics supplied after build",
                analytics_root=analytics_root,
            )
        if not ares.ok or not ares.record:
            return LoopResult(
                False,
                _fail(cycle, "measuring", "; ".join(ares.errors)),
                ares.errors,
            )
        cycle["analytics_ids"] = [ares.record["id"]]
        log("MEASURE", True, analytics_id=ares.record["id"], status=ares.record.get("status"))

        # LEARN
        _set_state(cycle, "learning")
        lres = generate_learning_from_analytics(
            ares.record["id"], analytics_root=analytics_root
        )
        if not lres.ok or not lres.learning:
            return LoopResult(
                False,
                _fail(cycle, "learning", "; ".join(lres.errors)),
                lres.errors,
            )
        cycle["learning_ids"] = [lres.learning["id"]]
        log("LEARN", True, learning_id=lres.learning["id"])
        log("FEEDBACK", True, note="learning stored for knowledge index (advisory)")

        _set_state(cycle, "completed")
        cycle["status"] = "completed"
        cycle["outcome"] = "execute_build_measured"
        cycle["completed_at"] = _now()
        if persist:
            upsert_cycle(cycle, cycles_root)
        return LoopResult(True, cycle)

    except Exception as e:
        c = _fail(cycle, cycle.get("state") or "unknown", str(e))
        if persist:
            upsert_cycle(c, cycles_root)
        return LoopResult(False, c, errors=[str(e)])
