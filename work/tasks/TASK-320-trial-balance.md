---
id: TASK-320
title: "A-02 first slice: the trial balance of record, versions, leadsheets and annotations"
spec: SPEC-309
acceptance_criteria: [AC-1, AC-2, AC-4, AC-5, AC-6, AC-7, AC-8]
risk_zone: red
status: done
branch: task-320-trial-balance
worktree: spec005
created: 2026-10-21
updated: 2026-10-21
---

## Plan
- **Migration 0073:** `trial_balances`, `trial_balance_versions` and `trial_balance_annotations`. Rollback is the downgrade (it drops the three tables). No existing table changes.
- **Ledger:**
  - `trial_balances.py` (pure compute plus a dependency-free service) and `tb_repository.py`;
  - the models;
  - registry rows (one column, `current_version_no`, is updatable);
  - api exports, including the `register_adjustment_source` slot.
- **Assurance:** `trial_balance.py` (authorise, then ledger) and `routes.py`. Matrix file: `assurance.yaml`, with `trial_balance.read`, `trial_balance.adopt` and `trial_balance.annotate`.
- **Web:** `TrialBalance.tsx`, `amounts.ts` (shared with `Workpaper.tsx`), the route and the tab.

## Definition of done
- [x] `tests/unit/ledger/test_trial_balances.py` (7) and the pinned gate tests pass.
- [x] A local DB smoke test passes:
  - adopt, annotate and read back (32 accounts, balanced);
  - same-snapshot and Final refused;
  - UPDATE on versions refused.
- [x] `spec309trialbalance.test.tsx` (5) and `spec308workpapers.test.tsx` pass.
- [x] check-fast passes.
