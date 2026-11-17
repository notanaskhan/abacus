---
id: TASK-8427
title: "G-04-T12: Usage alert evaluator"
spec: SPEC-680
acceptance_criteria: [AC-35, AC-38, AC-39]
risk_zone: amber
status: in-review
branch: g04-t12-usage-alerts
worktree: /Users/ayushkbhatia/Accrued/abacus-s48
created: 2026-11-17
updated: 2026-11-17
plan_key: G-04-T12
---

## Objective
Spec section: docs/plan/epics/G-04.md §4.5, §4.8. Usage alert evaluator: ledger-driven threshold crossings once per rule per usage month, firm and engagement notifications through C16 kinds, banner facts for ADM-14 b and c, nightly reconcile.

## Plan (amber)
1. `platform/usage_alerts.py`: `evaluate(tenant)` compares this usage month's rollup minutes with the enabled rules (code's minutes) and each engagement's budget; a first crossing writes one `usage_alert_events` row (the unique index makes replays and reconciles write nothing) and emits `usage.threshold_crossed` (rule people + partners/firm-admin groups) or `engagement_budget.threshold_crossed` (managers, else leads); `banner_facts` for ADM-14 b/c; `evaluate_all` for every firm.
2. Triggers: `metering.on_run_completed` evaluates after a new posting; `UsageAlertReconcileWorkflow` nightly on the Schedule `usage_alerts:platform` (`platform.jobs`).
3. C16: kinds `usage_threshold_crossed` and `engagement_budget_threshold_crossed` (in-app + email default) with templates.
4. Tests: `tests/unit/platform/test_g04t12_usage_alerts.py`.

## Progress log
- `2026-11-17` — Built in the S48 sequential stack (DEC-5419). Lint, pyright, banned patterns clean; app and worker import. Partial: ADM-14's banner facts are a service function (no route yet; G-04-T18 reads them); the remaining G-04 C16 kinds (plan_request.*, support.replied, usage.scheduled_paused) are not catalogued yet; the new workflow has no replay history yet (end pass); email templates are DB rows for G-04-T20. Gates and tests run once at the S48 end pass (build first, test last).
