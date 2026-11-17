---
id: TASK-8430
title: "W-01-T19: Journey E2E and parity for Connect"
spec: SPEC-659
acceptance_criteria: [AC-1, AC-2]
risk_zone: green
status: in-review
branch: w01-t19-journeys-parity
worktree: /Users/ayushkbhatia/Accrued/abacus-s48
created: 2026-11-17
updated: 2026-11-17
plan_key: W-01-T19
---

## Objective
Spec section: docs/plan/epics/W-01.md §7 item 1. Journey E2E and parity: j14 3, 3b, 3c, 3d and j01 4 with INV-1..5 and axe; lock WB-10 a–i and WB-11 a–f at Tier C; Tier D.

## Plan (green)
1. `e2e/journeys/J14-firm-admin.spec.ts`: describe "J14 integration admin (W-01)" with the four named tests on the harness (axe and INV-1..5 after each step): j14 3 (WB-10 b, WB-11 d client-ledger app with no connect control), 3b (WB-10 d, WB-11 f for Hannah), 3c (WB-10 f, WB-11 c token expired · 1 run failed · 5 agents paused · Reconnect…), 3d (WB-11 e typed-name disconnect).
2. `e2e/journeys/J01-firm-onboarding.spec.ts`: "j01 4" on WB-10 c (the six connections).
3. `docs/screens/WB-10.md`, `WB-11.md`: `## Parity` tables, a–i and a–f at C (locked), host at D.
4. Fixture project walks them; staging and canary are `test.fixme` until the W-01-T21 canary flip.

## Progress log
- `2026-11-17` — Built in the S48 sequential stack (DEC-5422). eslint and prettier clean; parity row and route tests pass (71). Not run: the Playwright journeys themselves (end pass) and the staging walk with real auth (after the canary flip, a human step). Partial: j14 3's ADM-08 failed-test-by-code check and the Sage Intacct detail with Bluestem's company are not in the fixtures (only CCH's detail is), so j14 3 asserts the ERP tile and the client-ledger auth line on WB-11 d; parity diffs are measured on `parity-screens` in the end pass. Gates and tests run once at the S48 end pass (build first, test last).
