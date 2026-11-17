---
id: TASK-8428
title: "G-04-T08: Run admission over-limit hook"
spec: SPEC-680
acceptance_criteria: [AC-37]
risk_zone: red
status: in-review
branch: g04-t08-over-limit-admission
worktree: /Users/ayushkbhatia/Accrued/abacus-s48
created: 2026-11-17
updated: 2026-11-17
plan_key: G-04-T08
---

## Objective
Spec section: docs/plan/epics/G-04.md §4.5 (AC-37). Run admission over-limit hook: with platform.plan_usage on and At 100% set to Pause scheduled agents only, schedule-triggered runs are refused at admission with state_reason budget_100pct at or over included; manual, session, triggered and event-policy runs and open sessions continue; one usage.scheduled_paused notice per usage month.

## Plan (red)
1. `platform.api.over_limit_policy` (plan_usage): the At 100% choice under `platform.plan_usage` and whether this usage month's minutes reach the included minutes.
2. `agents/budget_admission.py`: `refusal` (only `schedule` is pausable), `admission_refusal(tenant, trigger_kind)` for the run-start path, `announce_pause` (one `usage.scheduled_paused` per usage month, deduplicated on a tenant counter; audit `usage.scheduled_run_paused`).
3. C16 kind `usage_scheduled_paused` (firm admins, in-app).
4. Tests: `tests/unit/agents/test_g04t08_budget_admission.py`.

## Progress log
- `2026-11-17` — Built in the S48 sequential stack (DEC-5420). Lint, pyright, banned patterns clean. Red: security review in the end pass. Partial: no start path creates schedule-triggered runs yet (W-03 adds agent schedules), so `admission_refusal` is not called anywhere yet; W-03's schedule start must call it before inserting the run and record the refusal with `state_reason = budget_100pct`. The Aug 24 train merge is a human step. Gates and tests run once at the S48 end pass (build first, test last).
