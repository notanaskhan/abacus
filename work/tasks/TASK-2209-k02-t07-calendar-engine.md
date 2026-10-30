---
id: TASK-2209
title: K-02-T07 due-date and clock engine
spec: SPEC-500
acceptance_criteria: [AC-21, AC-22, AC-23, AC-24, AC-25, AC-26]
risk_zone: amber
status: in-review
epic: K-02
plan_key: K-02-T07
branch: s17-k02-t07
created: 2026-10-30
updated: 2026-10-30
---

## Objective
The C21 part A calendar in `practice`: original and extended due dates by form and period end,
IRC §7503 weekend and legal-holiday roll (federal and DC), disaster postponements by state and
county window, `add_business_days`, calendar-day clocks (AU-C 230 and 265 +60, FTC +30, 8879
retention end); `GET /v1/due-dates`; results stamped with reference-set version ids and
`inputs_hash` (K-02 §3 F2, §4.4, §4.5).

Acceptance (backlog row): "Pure functions return Sep 15, 2026 for Ridgeline's extended 1065 and
Nov 16, 2026 for a June-30 Form 990, and the same inputs always give the same inputs_hash."

## Plan (amber)
- `practice/compute/calendar.py` (new, pure): `add_months`, `roll`, `add_business_days`,
  `pick_rule`, `covers`, `postpone`, `due_dates`, `clock_due`, `inputs_hash`.
- `practice/due_dates.py` (new): reads sets through `platform.api.references_in_effect`
  (K-02-T05, stacked) and calls the engine. `practice/due_dates_routes.py` (new): the router moves
  out of the contract module.
- Additive contract fields: `DueDateExtension.day`, `DueDates.postponed_to`.
- `platform.api` exports the three payload models the calendar reads.
- No migration, no matrix or flag change. Generated client regenerates.
- Tests: `tests/unit/practice/test_k02t07_calendar.py` (US-2.1 cases and Hypothesis properties),
  `tests/integration/test_k02t07_due_dates.py` (Postgres probes, route); the C21 stub suite
  moves the due-dates route to live.
- Rollback: revert; the route returns to 501 and the API to `NotImplementedError`.

## Acceptance
| Check | Test |
|---|---|
| US-2.1 dates, fiscal vs calendar rules | `test_ac21_*` |
| §7503 roll, holidays from the database | `test_ac22_*` |
| Postponements | `test_ac23_*` |
| Clocks and business days | `test_ac24_*` |
| Same inputs, same hash | `test_ac25_*`, `test_ac26_due_dates_name_their_rules_and_hash_their_inputs` |
| Service and route | `test_ac26_*`, `test_inv4_*` |

## Progress log
- 2026-10-30: built in S17 Lane 2 on K-02-T05; tests written, run in the end review.
