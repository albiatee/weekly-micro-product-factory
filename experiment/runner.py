"""P5 Experiment Runner — limited real execution under Policy/Guardrails.

Runs a constrained experiment lifecycle:
  Opportunity → Spec → start → artifact/metrics → complete → Policy *evaluation* only

Does NOT: live publish to public channels, bypass Policy, build production products,
or write execute decisions that trigger Path A.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from opportunity.evidence import is_evidence_ready
from opportunity.store import list_opportunities
from policy.evaluate import PolicyResult, evaluate_decision

from .pipeline import (
    complete_experiment,
    create_experiment,
    record_results,
    start_experiment,
)
from .store import get_experiment

ROOT = Path(__file__).resolve().parents[1]
RUNS_DIR = ROOT / "data" / "experiment_runs"

# v0.1 allowed runner types (limited)
ALLOWED_RUNNER_TYPES = frozenset({"smoke_page", "manual_pilot", "waitlist"})


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class RunResult:
    ok: bool
    experiment: dict[str, Any] | None = None
    run_dir: str | None = None
    artifact_path: str | None = None
    metrics: dict[str, Any] | None = None
    policy: dict[str, Any] | None = None
    errors: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def _run_dir(exp_id: str, root: Path | None = None) -> Path:
    base = (root or ROOT) / "data" / "experiment_runs" / exp_id
    return base


def _write_smoke_artifact(
    run_dir: Path,
    *,
    opportunity: dict[str, Any],
    experiment: dict[str, Any],
) -> Path:
    """Create a real minimal local HTML artifact (not Path A publish)."""
    run_dir.mkdir(parents=True, exist_ok=True)
    title = (opportunity.get("title") or opportunity.get("problem") or "Experiment")[:80]
    hyp = experiment.get("hypothesis_test") or ""
    html = f"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{_esc(title)}</title>
<style>
body{{font-family:system-ui,sans-serif;max-width:40rem;margin:2rem auto;padding:0 1rem;line-height:1.6}}
.badge{{display:inline-block;background:#e2e8f0;padding:.2rem .5rem;border-radius:999px;font-size:.75rem}}
input,button{{font:inherit;padding:.5rem .75rem;margin-top:.5rem}}
</style>
</head>
<body>
<p class="badge">experiment smoke · not a production publish</p>
<h1>{_esc(title)}</h1>
<p>{_esc(hyp[:400])}</p>
<form id="f" onsubmit="return false">
  <label>اهتمام / بريد (محلي فقط)<br>
  <input type="email" id="email" placeholder="you@example.com"></label><br>
  <button type="button" id="btn">سجّل اهتمام</button>
</form>
<p id="msg"></p>
<script>
(function(){{
  var n = 0;
  document.getElementById('btn').onclick = function(){{
    n += 1;
    try {{ localStorage.setItem('exp_signups', String(n)); }} catch(e) {{}}
    document.getElementById('msg').textContent = 'تم التسجيل محلياً #' + n + ' (لا يُرسل لخادم)';
  }};
}})();
</script>
</body>
</html>
"""
    path = run_dir / "index.html"
    path.write_text(html, encoding="utf-8")
    meta = {
        "created_at": _now(),
        "opportunity_id": opportunity.get("id"),
        "experiment_id": experiment.get("id"),
        "channel": "local_artifact_only",
        "not_public_publish": True,
    }
    (run_dir / "run_meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return path


def _esc(s: str) -> str:
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _default_criteria() -> tuple[dict[str, Any], dict[str, Any]]:
    success = {"metric": "signups", "op": ">=", "value": 5}
    failure = {"metric": "signups", "op": "<", "value": 1}
    return success, failure


def run_experiment(
    opportunity_id: str,
    *,
    experiment_type: str = "smoke_page",
    hypothesis_test: str | None = None,
    measurement_plan: str | dict[str, Any] | None = None,
    success_criteria: dict[str, Any] | str | None = None,
    failure_criteria: dict[str, Any] | str | None = None,
    target_population: str | None = None,
    metrics: dict[str, Any] | None = None,
    metrics_file: Path | None = None,
    created_by: str = "system:experiment_runner",
    opportunities_root: Path | None = None,
    experiments_root: Path | None = None,
    runs_root: Path | None = None,
    evaluate_policy: bool = True,
    dry_run: bool = False,
) -> RunResult:
    """Execute limited experiment. Metrics must be supplied (or metrics_file).

    Policy evaluation is advisory only — does not create execute/build.
    """
    notes: list[str] = []
    if experiment_type not in ALLOWED_RUNNER_TYPES:
        return RunResult(
            False,
            errors=[
                f"experiment_type {experiment_type!r} not allowed in runner v0.1; "
                f"allowed={sorted(ALLOWED_RUNNER_TYPES)}"
            ],
        )

    opps = list_opportunities(opportunities_root)
    opp = opps.get(opportunity_id)
    if not opp:
        return RunResult(False, errors=[f"opportunity not found: {opportunity_id}"])

    ready, errs = is_evidence_ready(opp)
    if not ready:
        return RunResult(False, errors=["opportunity not evidence-ready"] + list(errs))

    succ, fail = _default_criteria()
    if success_criteria is not None:
        succ = success_criteria
    if failure_criteria is not None:
        fail = failure_criteria

    plan = measurement_plan or {
        "metric": "signups",
        "method": "manual_or_file_metrics",
        "notes": "Count interested signups during observation window; local artifact only",
    }

    created = create_experiment(
        opportunity_id,
        experiment_type=experiment_type,
        hypothesis_test=hypothesis_test
        or (
            f"If we expose a minimal smoke page for this problem, the target audience "
            f"will show measurable interest (signups)."
        ),
        measurement_plan=plan,
        success_criteria=succ,
        failure_criteria=fail,
        target_population=target_population
        or str(opp.get("audience") or opp.get("target_user") or "target users"),
        channel="local_artifact_only",
        created_by=created_by,
        opportunities_root=opportunities_root,
        experiments_root=experiments_root,
        dry_run=dry_run,
    )
    if not created.ok or not created.experiment:
        return RunResult(False, errors=created.errors)

    exp = created.experiment
    exp_id = exp["id"]

    if dry_run:
        notes.append("dry_run: experiment planned only; no start/artifact/metrics")
        return RunResult(True, experiment=exp, notes=notes)

    # Real limited artifact
    base_runs = runs_root or (ROOT / "data" / "experiment_runs")
    run_dir = base_runs / exp_id
    artifact = None
    if experiment_type in ("smoke_page", "waitlist"):
        artifact = _write_smoke_artifact(run_dir, opportunity=opp, experiment=exp)
        notes.append(f"artifact written: {artifact}")
    else:
        run_dir.mkdir(parents=True, exist_ok=True)
        notes.append("manual_pilot: no HTML artifact; metrics still required")

    started = start_experiment(
        exp_id,
        opportunities_root=opportunities_root,
        experiments_root=experiments_root,
    )
    if not started.ok or not started.experiment:
        return RunResult(
            False,
            experiment=exp,
            run_dir=str(run_dir),
            artifact_path=str(artifact) if artifact else None,
            errors=started.errors,
            notes=notes,
        )
    exp = started.experiment

    # Collect metrics — must be real inputs, not invented
    collected: dict[str, Any] | None = None
    if metrics is not None:
        collected = dict(metrics)
        notes.append("metrics from caller")
    elif metrics_file is not None and metrics_file.exists():
        try:
            loaded = json.loads(metrics_file.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                collected = loaded
                notes.append(f"metrics from file {metrics_file}")
        except (json.JSONDecodeError, OSError) as e:
            return RunResult(
                False,
                experiment=exp,
                run_dir=str(run_dir),
                errors=[f"metrics_file unreadable: {e}"],
                notes=notes,
            )
    else:
        default_metrics_path = run_dir / "metrics.json"
        if default_metrics_path.exists():
            try:
                loaded = json.loads(default_metrics_path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    collected = loaded
                    notes.append("metrics from run_dir/metrics.json")
            except (json.JSONDecodeError, OSError) as e:
                return RunResult(False, experiment=exp, errors=[str(e)], notes=notes)

    if collected is None:
        notes.append(
            "no metrics yet — experiment left running; "
            "write data/experiment_runs/<id>/metrics.json then re-run complete step"
        )
        return RunResult(
            True,
            experiment=exp,
            run_dir=str(run_dir),
            artifact_path=str(artifact) if artifact else None,
            metrics=None,
            notes=notes,
        )

    # Persist metrics copy in run dir
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "metrics.json").write_text(
        json.dumps(collected, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    rec = record_results(
        exp_id,
        metrics=collected,
        experiments_root=experiments_root,
    )
    if not rec.ok or not rec.experiment:
        return RunResult(
            False,
            experiment=exp,
            run_dir=str(run_dir),
            metrics=collected,
            errors=rec.errors,
            notes=notes,
        )
    exp = rec.experiment

    done = complete_experiment(
        exp_id,
        opportunities_root=opportunities_root,
        experiments_root=experiments_root,
    )
    if not done.ok or not done.experiment:
        return RunResult(
            False,
            experiment=exp,
            run_dir=str(run_dir),
            metrics=collected,
            errors=done.errors,
            notes=notes,
        )
    exp = done.experiment

    policy_payload = None
    if evaluate_policy:
        pr: PolicyResult = evaluate_decision(
            experiment=exp,
            opportunity=opp,
            metrics=collected,
        )
        policy_payload = {
            "verdict": pr.verdict,
            "rule_hits": pr.rule_hits,
            "reason": pr.reason,
            "risk": pr.risk,
            "advisory": True,
            "note": "Policy evaluation only — does not authorize build/publish",
        }
        notes.append(f"policy advisory verdict={pr.verdict}")

    return RunResult(
        True,
        experiment=exp,
        run_dir=str(run_dir),
        artifact_path=str(artifact) if artifact else None,
        metrics=collected,
        policy=policy_payload,
        notes=notes,
    )


def complete_with_metrics(
    experiment_id: str,
    metrics: dict[str, Any],
    *,
    opportunities_root: Path | None = None,
    experiments_root: Path | None = None,
    runs_root: Path | None = None,
    evaluate_policy: bool = True,
) -> RunResult:
    """Attach metrics to a running experiment and complete + policy evaluate."""
    exp = get_experiment(experiment_id, experiments_root)
    if not exp:
        return RunResult(False, errors=[f"experiment not found: {experiment_id}"])
    if exp.get("status") not in ("running", "planned"):
        return RunResult(
            False,
            experiment=exp,
            errors=[f"cannot complete from status {exp.get('status')!r}"],
        )

    if exp.get("status") == "planned":
        st = start_experiment(
            experiment_id,
            opportunities_root=opportunities_root,
            experiments_root=experiments_root,
        )
        if not st.ok:
            return RunResult(False, experiment=exp, errors=st.errors)
        exp = st.experiment or exp

    base = runs_root or (ROOT / "data" / "experiment_runs")
    run_dir = base / experiment_id
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    rec = record_results(
        experiment_id,
        metrics=metrics,
        experiments_root=experiments_root,
    )
    if not rec.ok:
        return RunResult(False, experiment=exp, errors=rec.errors)

    done = complete_experiment(
        experiment_id,
        opportunities_root=opportunities_root,
        experiments_root=experiments_root,
    )
    if not done.ok or not done.experiment:
        return RunResult(False, experiment=rec.experiment, errors=done.errors)

    exp = done.experiment
    policy_payload = None
    if evaluate_policy:
        opp = list_opportunities(opportunities_root).get(exp.get("opportunity_id") or "")
        pr = evaluate_decision(experiment=exp, opportunity=opp, metrics=metrics)
        policy_payload = {
            "verdict": pr.verdict,
            "rule_hits": pr.rule_hits,
            "reason": pr.reason,
            "risk": pr.risk,
            "advisory": True,
        }

    return RunResult(
        True,
        experiment=exp,
        run_dir=str(run_dir),
        metrics=metrics,
        policy=policy_payload,
    )
