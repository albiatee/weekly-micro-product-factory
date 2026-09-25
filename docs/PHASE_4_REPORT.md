# PHASE 4 REPORT — Experiment Engine

## Objective

Auditable experiments with predefined success/failure criteria, readiness gates, result capture, and no Phase 5 decisions.

## Inspected

Existing `experiment/` package (planned/running/completed/aborted), `contracts` types, `manage_experiments.py`, Phase 3 `is_evidence_ready` on start.

## Files changed / added

- `contracts/constants.py` — expanded `EXPERIMENT_TYPES`
- `experiment/constants.py` — immutability set
- `experiment/build.py` — criteria, population, assumptions_tested
- `experiment/readiness.py` — **new**
- `experiment/pipeline.py` — readiness on start, duplicate running guard, observations, `update_experiment_fields`
- `scripts/manage_experiments.py` — CLI fields + inspect
- `tests/test_experiment_engine_phase4.py` — **new**
- `tests/test_experiments.py` — criteria defaults for fixtures
- `docs/EXPERIMENT_ENGINE.md`, `docs/PHASE_4_REPORT.md`

## Lifecycle

planned → running → completed | aborted

## Readiness

`is_experiment_ready` + opportunity evidence-ready + no second running exp per opportunity.

## Tests

See full suite output in Phase 4 completion message.

## Not implemented

Phase 5 Decision Gate, production, distribution, analytics, LLM evaluation.

## Compatibility

Backward-compatible experiment statuses; new criteria required **before start**; legacy `success_threshold` still accepted as success_criteria source.


## Git checkpoint (pre–Phase 5)

- **Tests at checkpoint:** 178 passed, 0 failed, 0 skipped
- **Scope:** Phases 2–4 (Signal Quality, Opportunity Evidence, Experiment Engine) + baseline docs
- **Excluded:** unrelated `products/weekly` deletions (restored); Phase 5+ code
- Commit hash and push recorded after successful commit on `main`.
