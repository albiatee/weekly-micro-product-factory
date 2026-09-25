# PROJECT BASELINE — Phase 1

**Date:** 2026-09-25  
**Branch:** `main` (aligned with `origin/main` after merge `9ebd468`)  
**VERSION:** `1.0.0`  
**Scope:** Audit only. No feature work. Phase 2 not started.

---

## 1. Repository identity

One repo, **two independent paths**:

| Path | Name | Entry | Output |
|------|------|-------|--------|
| **A** | Weekly Micro Product Factory | GitHub Issues + vote / manual workflow | `products/weekly/<week_id>/` HTML |
| **B** | V2 AI Market Opportunity Factory | Signals → … → Learning → Hints | Auditable decisions; optional `products/bridge/` on execute |

Documented in `README.md` and `docs/OPERATING_RULES.md`.

**Rule:** Issue votes and RSS volume are **not** market validation by themselves.

---

## 2. Git / working tree health

| Item | Status |
|------|--------|
| HEAD | `9ebd468` merge of V2 (`3afef75`) with remote weekly products |
| Remote sync | `main...origin/main` (clean tracking at baseline time) |
| Uncommitted | Local **deletes** of `products/weekly/.gitkeep`, `2026-w38/*`, `2026-w39/*` only — **do not commit** without intent; restore from git if accidental |
| V2 commit | `3afef75 feat(v2): add AI Market Opportunity Factory loop (Phases 1–9)` on remote |

**Action:** Prefer `git checkout -- products/weekly/` if those deletes were unintended local cleanup.

---

## 3. What works today

### Path A (weekly factory)
- Workflows: `weekly-build.yml`, `issue-intake.yml`, stats refresh, tests workflow present.
- Templates: `calculator`, `landing-page`, `weekly-tracker`.
- Agents: triage, diversity, content, design, security, adversarial critic.
- Published weeks on tree include **2026-w38-i1 … 2026-w56** (catalog + stats).
- Optional LLM via env keys; deterministic templates as fallback.

### Path B (V2 loop — code present)
| Stage | Package / entry | Present |
|-------|-----------------|--------|
| Contracts | `contracts/validate.py`, `constants.py` | Yes |
| Signals | `discovery/` + `ingest_signals.py` + `collect_web_signals.py` | Yes |
| Opportunities | `opportunity/` + `generate_opportunities.py` | Yes |
| Experiments | `experiment/` + `manage_experiments.py` | Yes |
| Decisions | `decision/` + `manage_decisions.py` | Yes |
| Production bridge | `production/bridge.py` + `production_bridge.py` | Yes (`digital_micro`) |
| Distribution | `distribution/` + `manage_distribution.py` | Yes (manual-first) |
| Analytics / Learning | `analytics/` + `run_analytics.py` | Yes (no auto lifecycle change) |
| Discovery feedback | `discovery_feedback/` + `manage_discovery_feedback.py` | Yes (human accept) |
| Docs | `V2_ARCHITECTURE`, `DATA_CONTRACTS`, `PHASE2–9`, `OPERATING_RULES` | Yes |

**Imports:** All V2 pipelines import successfully.

**Lifecycle sample (Opportunity):**  
`draft → hypothesized → experimenting → decided → building | iterating | killed` (and `shipped` via bridge).

**Signal sources config:** Active feeds = `hnrss_ask`, `hnrss_q_invoice`, `hnrss_show`; noisy feeds in `disabled_feeds`.

---

## 4. What does not work / is incomplete

| Gap | Detail |
|-----|--------|
| **No Signal Quality Layer** | No formal intent taxonomy (Problem/Supply/Noise/…) in contracts or code; quality review was manual only |
| **Weak real discovery** | Pilot RSS (~20 signals): ~20% Problem-like, ~75% not opportunity-ready; `invoice` feed had 502; `freelance` was supply-heavy (now disabled) |
| **Empty V2 data stores** | No committed `data/*/index.json` business data (only `.gitkeep`); loop not proven end-to-end on production data |
| **Evidence gate soft** | Opportunities can be generated from signals without strong evidence model / strength scoring enforced at transition |
| **Experiment types** | Framework exists; low-cost experiment *types* (waitlist, interview, pre-order) not fully productized as first-class enums + gates |
| **decided as durable audit row** | Design preferred explicit `decided` recording; implementation leans transition + Decision entity (acceptable but audit UX can improve) |
| **Hardening debt** | Possible multiple `running` experiments per opportunity; partial-write orphan risk (signal/hint, bridge artifact) |
| **Path A ≠ Path B link** | Weekly issue acceptance does not flow through V2 opportunity/experiment contracts |
| **Analytics period** | Some CLI flags reserved / incomplete historically |

---

## 5. Tests

```text
python -m pytest tests/ -q --tb=line
→ 146 passed in ~29s
```

Coverage includes (non-exhaustive):

- `test_contracts`, `test_signal_discovery`, `test_web_rss_collector`
- `test_opportunity_engine`, `test_experiments`, `test_decisions`
- `test_production_bridge`, `test_distribution`
- `test_analytics_learning`, `test_discovery_feedback`
- Path A: `test_triage`, `test_diversity_analyzer`, `test_i18n`

**Note:** Suite is unit/integration in-process; full CLI system tests and real network RSS are limited/mocked for collector.

---

## 6. Known issues (prioritized)

### High (product risk, not test-red)
1. **Discovery quality bottleneck** — system can store noise; OPERATING_RULES forbid bulk `generate_opportunities` but enforcement is policy, not code.
2. **No automated qualification** before opportunity generation.

### Medium (engineering)
3. Concurrent / sequential `running` experiments on same opportunity not strictly blocked.
4. Atomicity gaps on multi-store writes (hint accept, bridge copy + status).
5. Local working-tree deletes under `products/weekly/` (w38/w39) — hygiene risk.
6. RSS `raw_text` often includes HN boilerplate (points, comments URL) — harms clarity/dedupe.

### Low
7. Dual documentation surface (many PHASE*.md + V2_ARCHITECTURE) — accurate but heavy.
8. `CONTRIBUTING.md` exists; keep aligned with OPERATING_RULES.

---

## 7. Risks

| Risk | If ignored |
|------|------------|
| Treating RSS/votes as demand | False opportunities → wasted experiments/production |
| Bulk opportunity generation | Pollutes `data/opportunities` and analytics |
| Skipping human review on hints | Feedback loop amplifies noise |
| Committing accidental product deletes | Catalog/Pages drift |
| Expanding features before pilot | Hardening cost without evidence the loop works in practice |

---

## 8. Recommendation — next step only

**Do not start unrelated features.**

**Recommended Phase 2 (when approved):** **Signal Quality** layer:

- Intent taxonomy (Problem, Question, Request, Complaint, Buying Intent, Workaround, Supply, Promotion, Noise)
- Evidence fields + strength rules
- Explicit **reject / qualify** path before opportunity generation
- Tests for rules; keep OPERATING_RULES as source of policy
- Improve sources only after qualification rules exist

**Do not** jump to Phase 10 pilot until qualification exists (or strictly manual selection of strong signals).

**Immediate hygiene (optional, still Phase 1 follow-up):** restore accidental `products/weekly` deletes if needed; leave V2 data empty until a controlled pilot.

---

## 9. Baseline verdict

| Criterion | Result |
|-----------|--------|
| Path A operational | **Yes** |
| Path B code + tests green | **Yes (146 passed)** |
| Closed-loop design documented | **Yes** |
| Production-grade market discovery | **Not yet** (quality + real E2E pilot missing) |
| Safe to proceed to Phase 2 Signal Quality | **Yes** |

**PHASE 1 COMPLETE — BASELINE DOCUMENTED.**  
**PHASE 2 NOT STARTED.**
