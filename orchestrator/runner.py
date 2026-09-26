"""Orchestrator runner — sequencing only."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from policy.config import load_config
from policy.evaluate import evaluate_decision
from policy.select import select_opportunities, score_opportunity, is_eligible

from discovery.quality import apply_quality, is_opportunity_eligible
from discovery.store import list_signals
from opportunity.pipeline import generate_from_signal_ids
from opportunity.store import list_opportunities
from opportunity.evidence import is_evidence_ready
from experiment.store import list_experiments, get_experiment
from decision.pipeline import create_decision

from .context import CycleContext
from .cycle import new_cycle_record
from .kill_switch import is_enabled
from .steps import steps_until, STEPS
from .store import upsert_cycle


def _log(cycle: dict[str, Any], step: str, ok: bool, **payload: Any) -> None:
    entry = {"step": step, "ok": ok, **payload}
    cycle.setdefault("step_log", []).append(entry)
    if ok:
        if step not in cycle.get("completed_steps", []):
            cycle.setdefault("completed_steps", []).append(step)
    cycle["current_step"] = step
    from datetime import datetime, timezone

    cycle["updated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _step_collect(ctx: CycleContext) -> None:
    """v0: optional network collect disabled by default; record store snapshot."""
    if not ctx.config.get("collect_on_cycle", False):
        _log(ctx.cycle, "COLLECT", True, note="skipped_collect_on_cycle_false", refs={})
        return
    # Network collect left off by default for safety
    _log(ctx.cycle, "COLLECT", True, note="collect_on_cycle_not_implemented_network", refs={})


def _step_qualify(ctx: CycleContext) -> None:
    signals = list_signals(ctx.signals_root)
    qualified = []
    for sid, sig in signals.items():
        s2 = apply_quality(dict(sig))
        if is_opportunity_eligible(s2):
            qualified.append(sid)
    ctx.signal_ids = qualified
    ctx.cycle.setdefault("refs", {})["qualified_signal_ids"] = qualified
    _log(ctx.cycle, "QUALIFY", True, refs={"qualified_count": len(qualified), "ids": qualified[:20]})


def _step_opportunity(ctx: CycleContext) -> None:
    """Generate only if no opportunities exist for qualified signals; else reuse store."""
    existing = list_opportunities(ctx.opportunities_root)
    # Prefer existing evidence-ready opps linked to our signal universe
    linked = []
    qset = set(ctx.signal_ids)
    for opp in existing.values():
        sids = set(opp.get("signal_ids") or [])
        if not qset or sids & qset or is_evidence_ready(opp)[0]:
            linked.append(opp)

    generated_ids = []
    # Only generate for qualified signals that have no opportunity yet
    have = set()
    for opp in existing.values():
        for s in opp.get("signal_ids") or []:
            have.add(s)
    to_gen = [s for s in ctx.signal_ids if s not in have]
    # Cap generation volume for safety in a cycle
    to_gen = to_gen[: int(ctx.config.get("max_opportunities_per_cycle", 1)) * 3]

    if to_gen:
        res = generate_from_signal_ids(
            to_gen,
            signals_root=ctx.signals_root,
            opportunities_root=ctx.opportunities_root,
            created_by="orchestrator:cycle",
            combine=False,
        )
        for item in res.accepted:
            oid = item["opportunity"]["id"]
            generated_ids.append(oid)

    existing = list_opportunities(ctx.opportunities_root)
    ctx.opportunity_ids = list(existing.keys())
    _log(
        ctx.cycle,
        "OPPORTUNITY",
        True,
        refs={"generated": generated_ids, "store_count": len(existing)},
    )


def _step_select(ctx: CycleContext) -> None:
    opps = list(list_opportunities(ctx.opportunities_root).values())
    selected = select_opportunities(opps, config=ctx.config)
    scores = {o["id"]: score_opportunity(o) for o in selected}
    ctx.opportunity_ids = [o["id"] for o in selected]
    ctx.cycle["selection"] = {
        "opportunity_ids": ctx.opportunity_ids,
        "scores": scores,
    }
    ctx.cycle["counters"]["opportunities"] = len(ctx.opportunity_ids)
    _log(ctx.cycle, "SELECT", True, refs=ctx.cycle["selection"])


def _step_experiment(ctx: CycleContext) -> None:
    """v0: do not auto-start live experiments. Attach completed experiments if present."""
    if not ctx.opportunity_ids:
        _log(ctx.cycle, "EXPERIMENT", True, note="no_opportunity_selected", refs={})
        return
    oid = ctx.opportunity_ids[0]
    exps = list_experiments(ctx.experiments_root)
    linked_completed = [
        e
        for e in exps.values()
        if e.get("opportunity_id") == oid and e.get("status") == "completed"
    ]
    if linked_completed:
        # pick stable id order
        linked_completed.sort(key=lambda e: e.get("id") or "")
        eid = linked_completed[0]["id"]
        ctx.experiment_ids = [eid]
        ctx.cycle["experiment_ids"] = [eid]
        ctx.cycle["counters"]["experiments"] = 1
        _log(ctx.cycle, "EXPERIMENT", True, refs={"experiment_id": eid, "source": "existing_completed"})
        return

    # No auto-create in v0 orchestrator (safety): record gap
    _log(
        ctx.cycle,
        "EXPERIMENT",
        True,
        note="no_completed_experiment_for_selected_opportunity; auto_start_disabled_v0",
        refs={"opportunity_id": oid},
    )


def _step_decide(ctx: CycleContext) -> None:
    if not ctx.experiment_ids:
        _log(ctx.cycle, "DECIDE", True, note="no_experiment", verdict="no_decision")
        return
    eid = ctx.experiment_ids[0]
    exp = get_experiment(eid, ctx.experiments_root)
    oid = (exp or {}).get("opportunity_id") or (ctx.opportunity_ids[0] if ctx.opportunity_ids else None)
    opp = list_opportunities(ctx.opportunities_root).get(oid) if oid else None

    result = evaluate_decision(
        experiment=exp,
        opportunity=opp,
        iteration_count=int(ctx.cycle.get("counters", {}).get("iterations") or 0),
        config=ctx.config,
    )
    ctx.cycle.setdefault("refs", {})["policy_verdict"] = result.verdict
    ctx.cycle["refs"]["rule_hits"] = result.rule_hits
    ctx.cycle["refs"]["policy_reason"] = result.reason
    ctx.cycle["refs"]["risk"] = result.risk

    # Persist Decision only when we have a terminal verdict with completed experiment
    # and not dry-run policy-only — actually dry-run may still write decision for audit
    # Contract: dry_run should avoid produce/publish; Decision record is OK for audit if enabled
    write_decision = result.verdict in ("execute", "iterate", "kill") and exp
    decision_id = None
    if write_decision and exp and oid:
        metrics = None
        if isinstance(exp.get("results"), dict):
            metrics = exp["results"].get("metrics", exp["results"])
        # create_decision requires human-like decided_by in current code — use policy string
        # may fail validation on decided_by — try policy: prefix
        try:
            dres = create_decision(
                opportunity_id=oid,
                verdict=result.verdict if result.verdict != "no_decision" else "kill",
                reason=f"[policy] {result.reason} | hits={result.rule_hits}",
                evidence_refs=[eid],
                decided_by="policy:policy_autonomous_factory_v0",
                experiment_id=eid,
                opportunities_root=ctx.opportunities_root,
                experiments_root=ctx.experiments_root,
                decisions_root=ctx.decisions_root,
            )
            if dres.ok:
                decision_id = dres.decision["id"]
                # enrich fields on stored decision if possible
                from decision.store import list_decisions, upsert_decision

                dec = list_decisions(ctx.decisions_root).get(decision_id)
                if dec:
                    dec["policy_version"] = ctx.config.get("policy_version")
                    dec["cycle_id"] = ctx.cycle["id"]
                    dec["rule_hits"] = result.rule_hits
                    upsert_decision(dec, ctx.decisions_root)
                ctx.decision_ids = [decision_id]
                ctx.cycle["decision_ids"] = [decision_id]
            else:
                ctx.cycle.setdefault("refs", {})["decision_errors"] = dres.errors
        except Exception as e:
            ctx.cycle.setdefault("refs", {})["decision_errors"] = [str(e)]

    _log(
        ctx.cycle,
        "DECIDE",
        True,
        verdict=result.verdict,
        rule_hits=result.rule_hits,
        reason=result.reason,
        decision_id=decision_id,
    )


def _step_blocked_side_effect(ctx: CycleContext, step: str) -> None:
    from guardrails.checks import check_produce_path, check_publish

    verdict = (ctx.cycle.get("refs") or {}).get("policy_verdict") or "no_decision"
    if step == "PRODUCE":
        gr = check_produce_path(
            verdict=verdict,
            dry_run=ctx.dry_run,
            criteria_snapshot=True,  # informational — real path not taken in dry_run
            metrics_snapshot={},
            build_template="static_html_microproduct",
            config=ctx.config,
        )
        _log(ctx.cycle, step, True, skipped=True, guardrail_blocks=gr.blocks, note="side_effects_disabled_v0")
        return
    if step == "PUBLISH":
        gr = check_publish(
            dry_run=ctx.dry_run,
            channel="github_pages",
            config=ctx.config,
            publishes_this_cycle=int(ctx.cycle["counters"].get("publishes") or 0),
            publishes_this_week=0,
        )
        _log(ctx.cycle, step, True, skipped=True, guardrail_blocks=gr.blocks)
        return
    _log(ctx.cycle, step, True, skipped=True, note="not_implemented_or_blocked_v0")


def run_cycle(
    *,
    dry_run: bool = True,
    stop_after: str | None = "DECIDE",
    config_path: Path | None = None,
    signals_root: Path | None = None,
    opportunities_root: Path | None = None,
    experiments_root: Path | None = None,
    decisions_root: Path | None = None,
    cycles_root: Path | None = None,
    force_enabled: bool = False,
    persist: bool = True,
) -> dict[str, Any]:
    config = load_config(config_path)
    if not force_enabled and not is_enabled(config) and not dry_run:
        # non-dry-run requires kill switch open
        cycle = new_cycle_record(
            policy_id=config["policy_id"],
            policy_version=config["policy_version"],
            dry_run=dry_run,
        )
        cycle["status"] = "aborted"
        cycle["abort_reason"] = "ORCHESTRATOR_ENABLED is false"
        if persist:
            upsert_cycle(cycle, cycles_root)
        return cycle

    # dry-run always allowed for inspection
    cycle = new_cycle_record(
        policy_id=config["policy_id"],
        policy_version=config["policy_version"],
        dry_run=dry_run,
    )
    ctx = CycleContext(
        cycle=cycle,
        config=config,
        dry_run=dry_run,
        stop_after=stop_after or config.get("default_stop_after_dry_run") or "DECIDE",
        signals_root=signals_root,
        opportunities_root=opportunities_root,
        experiments_root=experiments_root,
        decisions_root=decisions_root,
        cycles_root=cycles_root,
        force_enabled=force_enabled,
    )

    plan = steps_until(ctx.stop_after)
    handlers = {
        "COLLECT": lambda: _step_collect(ctx),
        "QUALIFY": lambda: _step_qualify(ctx),
        "OPPORTUNITY": lambda: _step_opportunity(ctx),
        "SELECT": lambda: _step_select(ctx),
        "EXPERIMENT": lambda: _step_experiment(ctx),
        "DECIDE": lambda: _step_decide(ctx),
        "PRODUCE": lambda: _step_blocked_side_effect(ctx, "PRODUCE"),
        "BUILD": lambda: _step_blocked_side_effect(ctx, "BUILD"),
        "PUBLISH": lambda: _step_blocked_side_effect(ctx, "PUBLISH"),
        "MEASURE": lambda: _step_blocked_side_effect(ctx, "MEASURE"),
        "LEARN": lambda: _step_blocked_side_effect(ctx, "LEARN"),
        "FEEDBACK": lambda: _step_blocked_side_effect(ctx, "FEEDBACK"),
    }

    try:
        for step in plan:
            handlers[step]()
        cycle["status"] = "completed"
    except Exception as e:
        cycle["status"] = "failed"
        cycle["abort_reason"] = str(e)
        _log(cycle, cycle.get("current_step") or "UNKNOWN", False, errors=[str(e)])

    if persist:
        upsert_cycle(cycle, cycles_root)
    return cycle
