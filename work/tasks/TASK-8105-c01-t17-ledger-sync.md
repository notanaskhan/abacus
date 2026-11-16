---
id: TASK-8105
title: "C-01-T17: LedgerSyncWorkflow: hourly CDC sync, Sync now, meter budget (red)"
spec: SPEC-655
acceptance_criteria: [AC-5]
risk_zone: red
status: in-review
branch: c01-t17-ledger-sync
worktree: /Users/ayushkbhatia/Accrued/abacus-s46
created: 2026-11-15
updated: 2026-11-15
plan_key: C-01-T17
---

## Objective
Keep every close-enabled entity's QuickBooks books fresh: an hourly tick in firm business hours
asks change-data-capture what changed, pulls only those datasets for the open close months into a
new immutable monthly set, meters the calls, and pauses safely on reauth, throttles and the budget.

## Plan (red: written before the build)
1. Migration **0891** `ledger_month_register` (expand-only): `gl_snapshots.kind` gains `month`
   (tb required for year and month); `sync_schedules` gains `retry_at`, `last_failure_code`.
2. `ledger/month_ledger.py` (+ `ledger.api`): `record_month_snapshot` writes the monthly
   `ledger_snapshots` row with its TB lines, `ledger_accounts` and the month register (GL snapshot
   kind `month`, register fields), carrying forward any dataset CDC did not name; validated
   before any row (TB `validate`, register footing in natural signs); content digest dedups.
3. `connections/ledger_sync.py`: scope slot (`register_sync_scope`, filled by closes), schedules,
   `plan_tick`, `sync_entity`, meter, pause/fail paths, `sync_facts`, Sync now service, the two
   activities; `ledger_sync_types.py`; `ledger_sync_workflow.py` (`LedgerSyncWorkflow`, signals,
   continue-as-new every 24 ticks).
4. `ledger_sync_contract.py`: the C-01-T07 stubs now serve status and Sync now.
5. `closes/sync_scope.py`: unlocked, ended months, latest two per entity.
6. Events `ledger_sync.paused` (C16 `ledger_sync_paused`) and `change_event.detected` (ADR-041).
7. Tests: `tests/unit/connections/test_c01t17_sync_rules.py`, `tests/integration/test_c01t17_ledger_sync.py`,
   `tests/workflows/test_c01t17_ledger_sync_{timer,replay}.py`; recorder
   `abacus_tools.workflows.record_ledger_sync` (history recorded at the end pass).
Rollback: revert; migration 0891 downgrades while no month register exists. Dark behind
`connections.ledger_sync` (default off) and the live-ledger kill switch.

## Progress log
- `2026-11-15` — Planned at the S46 kickoff (#2053); plan written above before building.
- `2026-11-15` — Built as planned (DEC-5076). API import check clean. Not run: unit, integration
  and workflow tests, the history recording, pyright and the red-diff security review (end pass).
- **Open:** a live Intuit sandbox run needs F-09-T05's sandbox company. The workflow is started by
  Sync now (`signal_with_start`) and `ensure_sync_workflow`; wiring the latter into close
  generation is left to C-01-T42's live swap (a dispatch from a request path needs Temporal).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-5076 | Month set = TB + accounts + register in one immutable set with carry-forward; scope slot; budget pause; Sync now id | no |
