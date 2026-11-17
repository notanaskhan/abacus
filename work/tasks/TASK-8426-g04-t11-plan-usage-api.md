---
id: TASK-8426
title: "G-04-T11: Plan and usage API"
spec: SPEC-680
acceptance_criteria: [AC-27, AC-28, AC-29, AC-32, AC-33, AC-34, AC-40, AC-41]
risk_zone: amber
status: in-review
branch: g04-t11-plan-usage-api
worktree: /Users/ayushkbhatia/Accrued/abacus-s48
created: 2026-11-17
updated: 2026-11-17
plan_key: G-04-T11
---

## Objective
Spec section: docs/plan/epics/G-04.md §3 (ADM-14). Plan and usage API: GET plan with seats, modules, term, renewal and Workbench active; budget-alert settings with version and fresh MFA; engagement default and alerting rows through visible(); plan requests with partner approval; billing-rates provider slot with a synthetic-only fake.

## Plan (amber)
1. `platform/plan_usage.py`: plan (current entitlement version, seats in use from identity's `seats_in_use`, pending seats in open requests, enabled modules, billing contact, renewal in days, Workbench activity through `register_workbench_activity`); billing contact; budget alerts (policy row with version, 409 `stale_version`, rules upserted by threshold and the rest disabled, minutes from code); engagement budgets for this usage month through `engagement.read` (hidden engagements left out); billing rates through `register_billing_rates`, the figure book's fake card for a synthetic firm only; plan requests list, create, approve/decline by a partner who did not ask (`plan_request_self_approval`), withdraw by the requester; `plan_request.changed` events.
2. `identity.api.seats_in_use` (ADM-02's count).
3. Routes: the eleven ADM-14 routes live.
4. Tests: `tests/unit/platform/test_g04t11_plan_usage.py`.

## Progress log
- `2026-11-17` — Built in the S48 sequential stack (DEC-5418). Lint, pyright, banned patterns clean (REVIEW-001 reserves `decide`, so the function is `settle_request`). Partial: the C13 gate for an awaiting request is not registered (platform may import only identity; review must register it from its side, G-04-T12 or a review-owned source); Workbench activity reads 0 until W-02 registers its count; renewal_in_days counts calendar days from the firm's today. Gates and tests run once at the S48 end pass (build first, test last).
