---
id: TASK-3233
title: A-04-T28 Brightwater Hale planning events through service APIs
spec: SPEC-620
acceptance_criteria: [AC-22, AC-23]
risk_zone: green
status: in-review
epic: A-04
plan_key: A-04-T28
branch: s26b-a04-t28
worktree: /Users/ayushkbhatia/Accrued/abacus-s26
created: 2026-11-03
updated: 2026-11-03
---

# TASK-3233 · A-04-T28 · Planning events through service APIs

## Plan
- `scenarios/brightwater_hale/planning_slice.py` (opt-in `--slice planning`, needs `people`, `standards`, `review`): Northwind PY2025 on Mon Sep 14 under the demo clock: R1–R10 at 10:15 (AUD-08 a, R3 proposed significant, R5 rebuttal proposed), the internal-control paper EBP-140 with AUD-09's seven exceptions at 12:20, the `significant_risk` card routed at 12:31 and approved by Margaret Okonkwo at 4:40 PM, so G4 is met with the review slice's 11:12 materiality.
- Loader handlers call the services (`create_risk`, `edit_risk`, `request_risk_approval`, `create_workpaper`, `record_exceptions`, `decide_card`), exported through `assurance.api` and `workpapers.api`.
- Migration 0663 (expand-only): `control_exceptions.coso_component` nullable; AUD-09 shows "—" for exceptions still for resolution (DEC-2224). Service and contract types follow.
- Tests: `tests/unit/synthetic/test_a04t28_planning_slice.py`; `tests/integration/test_a04t28_planning_loaded.py` (loads at the 2026-09-24 snapshot; E0 at 9:24 AM precedes the day).

## Partial
- The agent runs (9:58 IC pack failure, 10:40 GAP waiting on two inputs, 12:40 SOC draft) and the 4:52 RA sign-off need the fake-model registry's artefacts and an RA paper; Sep 22 bridge letter and Sep 29 reliance; the 9:27 materiality v1 (the review slice proposes at 10:30).
- Granite Peak (10:12 AM 155,000; revenue and inventory significant; RCM and ITGC): DEC-1969, the BH FS groupings carry no pre-tax income line for its benchmark.
- `make fixtures` export of the planning artboards is not regenerated here.

## Progress log
- 2026-11-03: built; unit test 4 passed; the loaded test passes (G4 met; R1–R10; 7 exceptions, 3 without COSO). Found: the review slice cannot load past Apr 13 (its Feld checkpoint precedes the tax board's returns), so this slice carries its own idempotent basis events.
