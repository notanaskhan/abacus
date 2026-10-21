---
id: TASK-321
title: "A-02 ties: tie-out checks on the trial balance, and TB() working-paper cells"
spec: SPEC-310
acceptance_criteria: [AC-1, AC-2, AC-3, AC-4, AC-5]
risk_zone: amber
status: done
branch: task-321-ties
worktree: spec005
created: 2026-10-21
updated: 2026-10-21
---

## Plan
- **Migration 0074:** `tie_out_checks` and `tie_out_check_versions`. Rollback is the downgrade.
- **Workpapers:**
  - `ties.py` (the pure engine) and `tie_out.py` (service);
  - `tie_models.py` and `tie_repository.py`;
  - `checks_router`;
  - `TbSource` and `TB()` in `formulas.py`;
  - `tb_link` in the service, with the trial balance version in the content hash.
- **Matrix:** `tie_out_check.define`. Results are read with `trial_balance.read`.
- **Web:** `TieChecks.tsx` (the strip and the add sheet), and the Trial balance panel on `Workpaper.tsx`.

## Definition of done
- [x] `tests/unit/workpapers` (20) and the pinned gate tests pass.
- [x] A local DB smoke test passes: a check on the dev trial balance ties, and an uncited version is refused by CHECK.
- [x] `spec309trialbalance.test.tsx` and `spec308workpapers.test.tsx` (12) pass.
- [x] check-fast passes.
