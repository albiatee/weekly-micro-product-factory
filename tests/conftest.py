"""Shared pytest setup — Phase 4 experiment criteria defaults for fixtures."""
from __future__ import annotations

import experiment.pipeline as exp_pipeline

_DEFAULTS = {
    "success_criteria": {"metric": "signups", "min": 1, "window": "test"},
    "failure_criteria": {"metric": "signups", "below": 1, "window": "test"},
    "target_population": "Users affected by the opportunity problem (test fixture)",
}

_orig_create = exp_pipeline.create_experiment


def create_experiment_with_test_defaults(*args, **kwargs):
    for k, v in _DEFAULTS.items():
        kwargs.setdefault(k, v)
    return _orig_create(*args, **kwargs)


# Patch before test modules bind names when collected after conftest load.
# Tests that already imported create_experiment need explicit re-export patch:
exp_pipeline.create_experiment = create_experiment_with_test_defaults  # type: ignore[assignment]
