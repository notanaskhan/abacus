---
id: TASK-8429
title: "G-04-T13: Brightwater Hale plan and usage seed slice"
spec: SPEC-680
acceptance_criteria: [AC-27, AC-33, AC-35]
risk_zone: green
status: in-review
branch: g04-t13-seed-slices
worktree: /Users/ayushkbhatia/Accrued/abacus-s48
created: 2026-11-17
updated: 2026-11-17
plan_key: G-04-T13
---

## Objective
Spec section: docs/plan/epics/G-04.md §5. Brightwater Hale seed slices and fixture scenarios: plan row, alert rules and events, golden tests; make seed-demo and fixture mode agree.

## Plan (green)
1. `platform/g04_seed.py` (`platform.api.seed_synthetic_plan`, `seed_synthetic_alert`; synthetic firms only, idempotent).
2. `brightwater_hale/plan_usage_slice.py` (`--slice plan_usage`, needs `agent_minutes`): the plan row (46 seats, 20,000 included, anchor 15, renewal Jan 1, 2027), billing contact Grace Holloway, partner approver Margaret Okonkwo, engagement default 1,500 at 80%; rules 75 (GH, MO), 90 (+ FA), 100 (partners, firm admins); alerts 75% Oct 1 11:06 AM at 15,000 and 90% Oct 9 1:47 PM at 18,000.
3. Loader handlers `platform.plan_seeded` (writes the `plans` content row as the owner first) and `platform.usage_alert_seeded`.
4. `tests/unit/test_g04_contract_stubs.py`: 501 asserted only for the routes still stubbed (T09-T11 built the rest).
5. Tests: `tests/unit/platform/test_g04t13_plan_usage_slice.py` (slice ↔ figure book; 14,920, 18,240, 20,860, 404 of 490, 6 = 4 + 1 + 1).

## Progress log
- `2026-11-17` — Built in the S48 sequential stack (DEC-5421). Lint, pyright clean; the slice's three events load. Partial: the Oct 9 and Oct 14 ledger snapshots (18,240, 20,860) are not posted (the agent_minutes slice holds Oct 1 only), the Granite Peak engagement alert (Sep 30 → Hannah Leclerc), the Aug 17 support-session history, the Ines thread and the Feld session request are not seeded (no message text on file in this repo), staff fakes and the six console tenants stay typed fixtures (the seed writes only Brightwater Hale), and the pre-window support.panel_v2 shell seam is unchanged from P-01's interim frame. `make seed-demo` was not run. Gates and tests run once at the S48 end pass (build first, test last).
