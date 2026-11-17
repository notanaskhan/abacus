---
id: TASK-8445
title: C-01-T20 rest — the close run raises its exceptions (AC-31, "each open item traces to the procedure that raised it")
spec: SPEC-655
acceptance_criteria: [AC-31]
risk_zone: red
status: in-review
branch: s48r-c01-t20-issues
created: 2026-11-17
updated: 2026-11-17
plan_key: C-01-T20
---

## Objective
C-01-T20 (TASK-8109) left the automatic issue out: a procedure whose figure does not tie records
the result and "the reviewer raises the issue" (`closes/run_steps.py`). Its blockers are on main:
the `close` record type and `raise_exception` (C-01-T24, S47), `issue.create` for the close engine
(C-01-T29, S47), and the reconciliation service (C-01-T23, S48). Decided as DEC-5432.

## Plan (red: agents is PROTECTED)
1. **Scope (agents).** The close run executes as `engagements.run`, whose task scope has no
   `issue.create`. `register_plan_provider(key, provider, *, extra_scope=())` lets a provider add
   scope to its own runs only; the only scope a provider may add is `issue.create` (anything else
   refuses at registration). `start_engagement_run` writes `TASK_SCOPE` plus the provider's
   extra. `closes.run_plan` registers `closes.close_run` with `("issue.create",)`. Audit
   engagement runs keep their scope unchanged.
2. **Raising (closes).** `issues.raise_exception` takes an `Actor` (the run's agent context, as
   P-04's `create_issue` already does for T-04-T25's self-checks) and a `why`. The run steps
   raise a deduplicated engine exception (`close:<class>:<account>:-`, so a rerun or the CLS-04
   workpaper never raises it twice), severity medium (as CLS-04's schedule exception):
   - `close_reconcile_statement`: the newest version's tally is `off` → `bank_rec`,
     "‹account› does not reconcile".
   - `close_clear_third_party_sales`: the clearing account has not netted to zero → `bank_rec`,
     "‹account› has not cleared".
   - `close_amortize_prepaid`: any arrangement off → `schedule`, "‹account› does not tie to its
     schedule" (CLS-04's wording).
   The issue's internal note names the procedure ("Raised by the close run: ‹step›"), and its
   creator is the run's agent ("‹person› via Agent"), so each open item traces to its procedure.
3. **Run card.** `runs.run_card`'s `open_issues` is the close's open exceptions on the newest
   run (CLS-06's count, notes excluded); a read-only run keeps 0.
- **Tests:** `tests/integration/test_c01t20_auto_issues.py` (the scope rule included).
- **Rollback:** revert; no migration, no flag (behind `closes.engine` as before).

## Progress log
- 2026-11-17: planned (DEC-5432).
- 2026-11-17: built. Running the step handlers against Postgres for the first time found three
  defects on main, fixed here because the automatic issues depend on them: (1) the prepaid and
  depreciation steps inserted `close_schedule_results` without `engine_version` and
  `inputs_hash`, which 0885 made NOT NULL, so every such step failed; (2) every close step's
  `close_procedure.computed` audit put the step key (text) in its `Ref`, which takes only ids,
  counts and fingerprints, so every step failed at the audit write; it now carries the run id.
  (3) Found, not fixed: the depreciation step writes `tie` with an ending balance (the month's
  charge) that differs from the GL balance, which 0885's `tie <> 'tie' OR ending_balance =
  gl_balance` CHECK refuses; what depreciation's tie means needs C-01-T21's fixed-asset rule.
- Tests: integration `test_c01t20_auto_issues.py` 4 (scope rule, the schedule exception raised
  once with the run's agent as creator and the step in its note, the refusal without the
  provider's scope, the clearing exception); 515 closes and engagement-run neighbours green.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-5432 | A plan provider may add `issue.create`, and only that, to its runs' scope; the close run raises a deduplicated medium exception per procedure that does not tie | no |
