---
id: TASK-1244
title: Mutation wiring (nightly incremental, weekly sharded) and the protected floors file (Q-03-T026, Q-03-T027)
spec: SPEC-045
acceptance_criteria: [AC-8]  # stage 1 refuses a protected-file change; T026 and T027 are Q-03 §3.3 C1 (no spec AC of their own)
risk_zone: red
status: in-progress
epic: Q-03
plan_key: Q-03-T026; Q-03-T027
branch: s8b-quality
created: 2026-10-25
updated: 2026-10-25
---

## Objective
"Both jobs run for two consecutive weeks inside budget and publish survivors per module" (T026).
"A PR lowering any floor is refused by the hook and by CI" (T027).

## Plan (red zone)
- **Floors file:** `backend/mutation-thresholds.yaml` (new, protected): one floor per red scope
  (`identity/authz`, `kernel/db`, `kernel/uow`, `kernel/crypto`, `evidence`, `ai_gateway`,
  `audit_trail`, `compute`), all 0 until T051 sets them at the S11 baseline. A line format the hook
  can parse without PyYAML.
- **Guard:** `abacus_tools.quality.mutation_floors` compares the file with a base ref (default
  `origin/main`; format-only when the ref is unreachable, as on stage 1's shallow checkout) and
  fails on any lowered or removed floor. In `make check-fast`, and in the new
  `.github/workflows/mutation-floors.yml` against the pull request's base with full history.
- **Hook:** `.claude/hooks/_protected.py` `floor_violation()`; `protect_paths.py` rebuilds the file
  as a Write, Edit or MultiEdit would leave it and refuses a lowered floor; `guard_bash.py` refuses
  shell writes to the file (so every change goes through the edit hook). `protected-paths.md` lists it.
- **Driver:** `abacus_tools.quality.mutation` (`plan nightly|weekly`, `narrow`, `prepare`,
  `summarise`): the red scopes, the changed-files plan, line-balanced weekly shards, narrowing
  `[tool.mutmut] only_mutate` in the runner's copy, and the per-module survivors report
  (`mutants/**/*.meta`, mutmut's `exit_code_by_key`) checked against the floors.
- **Config:** `[tool.mutmut]` in `backend/pyproject.toml`; mutmut 3.8.0 (allowlisted, Sep 12 2026)
  is run with `uv run --with mutmut==3.8.0` in the workflows only; nothing is added to the lock.
- **Workflows:** `mutation-nightly.yml` (daily, 60-minute budget, red files changed in 24 h) and
  `mutation-weekly.yml` (Sundays, 4 shards, each under 4 h). Actions pinned by SHA as in ci.yml;
  read-only token; survivors as artifacts and job summaries.
- **Tests:** `tests/unit/quality/test_mutation_floors.py`, `tests/unit/quality/test_mutation_driver.py`,
  `tests/unit/tools/test_mutation_workflows.py`, hook cases in `tests/unit/quality/test_hooks.py`.
- **Decision:** DEC-365 (scope, suites, budgets, floor rule).
- **Rollback:** revert the commit; nothing in the database or the lock changes.

## Progress log
- 2026-10-25: plan written.
- 2026-10-25: built as planned (DEC-365). `pytest tests/unit/quality/test_mutation_floors.py
  tests/unit/quality/test_mutation_driver.py tests/unit/tools/test_mutation_workflows.py
  tests/unit/quality/test_hooks.py`: 209 passed (hook cases under the venv and the system python3).
  mutmut was **not run locally** (installing it needs Ayush's go-ahead); its config keys, the
  `.meta` layout (`exit_code_by_key`) and exit codes were read from mutmut's 3.8 source. The first
  nightly and weekly runs on main are the integration test; T026's acceptance (two weeks inside
  budget) starts then. Weekly shards over the current red files: 6,307 to 6,325 lines each.
  Human to-do: make `mutation floors only rise` a required check (repository ruleset).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-365 | Which suites mutation runs, budgets, the floor guard and its base | No (ADR-079) |
- 2026-10-26: security review fixes: the floors guard also refuses narrowing the mutation scope
  (`SCOPES`, `[tool.mutmut]`) and takes `--head-root`; `mutation-floors.yml` runs the base
  commit's guard from a worktree; the weekly run fails a floored scope no mutant measured; the
  edit hook protects the two scope blocks and reads only the protected files (a non-UTF-8 file no
  longer blocks edits). Not done: hash-pinning mutmut's dependencies (needs a resolve, i.e. a
  download). DEC-365 amended (the hooks are a guardrail, not a boundary).
