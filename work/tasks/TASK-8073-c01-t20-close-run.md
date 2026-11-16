---
id: TASK-8073
title: "C-01-T20: Close run plan provider and code procedures on the P-10 runtime"
spec: SPEC-655
acceptance_criteria: [AC-28, AC-29, AC-30, AC-31]
risk_zone: amber
status: in-review
branch: c01-t20-close-run
worktree: /Users/ayushkbhatia/Accrued/abacus-s46
created: 2026-11-15
updated: 2026-11-15
plan_key: C-01-T20
---

## Objective
The close run: code plans it from the pinned plan (task groups by procedure; scopes all, group,
failed only and accounts), P-10's engagement run executes it three at a time, deterministic
executors compute each procedure, a `close_treatment` card holds the third-party group, and only
a live person starts or retries a run.

## Plan (amber: written before the build)
1. `closes/procedures.py`: pure executors (reconcile, third-party clearing, prepaid amortisation,
   depreciation with the 2,500 capitalisation test, recategorisation rules, accrual roll).
2. `closes/run_plan.py`: provider `closes.close_run` (groups, scopes, decision step), the
   `close_treatment` decision kind (code options, code recommendation, reserved to a manager).
3. `closes/run_steps.py`: eight `close_*` run-step kinds over `ledger.api` reads and the close's
   records (new reconciliation versions; `close_schedule_results`).
4. `closes/runs.py` + contract routes: start (pin, Not started → In progress, P-10 start),
   history, run card, retry as a new task-scoped run. `agents/run_reads.py` (`run_step_rows`).
5. Tests: `tests/unit/closes/test_c01t20_close_run.py` (12 pass locally).
Rollback: revert; behind `closes.engine`.

## Progress log
- `2026-11-15` — Planned at the S46 kickoff (#2053).
- `2026-11-15` — Built (DEC-5060). App and worker import cleanly; unit tests pass.
- **Partial within the row:** issues raised automatically with source run and step need an
  `issue.create` record type for closes and the run's task scope (C-01-T23/T29); recategorisation
  rules and accrual estimates are firm content that arrive with C-01-T21/K-02, so those steps
  record the balance they read. Third-party clearing reads the clearing account's register; the
  processor file's gross-to-net lands with C-01-T23's upload path.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-5060 | Group table; retry as a task-scoped run; treatment card options; run reads via agents.api | no |
