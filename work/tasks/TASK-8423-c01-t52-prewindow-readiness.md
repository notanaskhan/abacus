---
id: TASK-8423
title: "C-01-T52: Pre-window production readiness"
spec: SPEC-655
acceptance_criteria: [AC-12]
risk_zone: red
status: in-review
branch: c01-t52-prewindow-readiness
worktree: /Users/ayushkbhatia/Accrued/abacus-s48
created: 2026-11-17
updated: 2026-11-17
plan_key: C-01-T52
---

## Objective
Spec section: docs/plan/epics/C-01.md §4.7, §7. Pre-window production readiness: C-01 migrations and the hourly sync promoted dark by Thu Aug 31, 2028; flag renewals to Thu Nov 16 in the Aug 24 train; Intuit tier and per-firm call budget confirmed (F-09); alarms for sync freshness, failure rate and meter budget; status-page component QuickBooks Online sync; kill-switch drill; POR-11 and close routes added to the Sep 2028 pen-test delta scope.

## Plan (red)
1. `connections/ledger_sync.py`: `_outcome` logs `ledger_sync.outcome` beside the counter at every entity sync; `ledger_sync.freshness` (minutes) at each success; `ledger_sync.meter_budget_exhausted` on the pause.
2. `infra/envs/staging/ledger_sync.tf`: log metric filters and alarms — failure rate (metric math over an hour), p95 freshness above 90 minutes for two hours, any meter-budget pause; thresholds in `variables.tf`.
3. `docs/runbooks/RB-92-ledger-sync.md` (+ README row): the three alarms, the kill switch and its staging drill, the status-page component, the promotion checklist.
4. `docs/plan/status/pen-test-deferral.md`: the C-01 delta-scope note (the test stays deferred, DEC-1389).

## Progress log
- `2026-11-17` — Built in the S48 sequential stack (DEC-5415). Lint, pyright and terraform fmt clean. Human/ops steps not done here: the production promotion by Thu Aug 31, the flag renewals in the Aug 24 train, F-09's Intuit tier confirmation, the staging kill-switch drill (RB-92 §4) and `terraform apply`; the status-page component is named in RB-92 (no status-page config lives in the repo). Gates and tests run once at the S48 end pass (build first, test last).
