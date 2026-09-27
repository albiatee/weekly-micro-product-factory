from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class CycleContext:
    cycle: dict[str, Any]
    config: dict[str, Any]
    dry_run: bool = True
    stop_after: str | None = "DECIDE"
    signals_root: Path | None = None
    opportunities_root: Path | None = None
    experiments_root: Path | None = None
    decisions_root: Path | None = None
    cycles_root: Path | None = None
    force_enabled: bool = False  # tests only
    persist: bool = True
    signal_ids: list[str] = field(default_factory=list)
    opportunity_ids: list[str] = field(default_factory=list)
    experiment_ids: list[str] = field(default_factory=list)
    decision_ids: list[str] = field(default_factory=list)
