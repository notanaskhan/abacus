---
id: TASK-2634
title: Q-04-T050 PW2 week-2 metrics read (W4 portal activation, W5 PBC through the portal)
spec: SPEC-000  # chapter 11 §11.6.2 and the Q-04-T050 row
acceptance_criteria: [AC-1]  # W4 and W5 per firm with their chapter 11 colour; any amber has an owner and action
risk_zone: amber
status: in-review
epic: Q-04
plan_key: Q-04-T050
branch: s21-q04-t050
worktree: /Users/ayushkbhatia/Accrued/abacus-s21
created: 2026-11-01
updated: 2026-11-01
---

## Objective
"W4 and W5 are reported per firm with their chapter 11 colour and any amber has an owner and
action." A Sprint 20 row pulled forward: with DEC-1530 the firm part runs on PF-X1 and is
reported as synthetic.

## Plan (amber)
- `backend/src/abacus/modules/platform/pilot_read.py` (new): `wedge_read`, `cross_firm`, `report`,
  exported from `platform.api`; read only over `pilot_metric_snapshots` and `pilot_enrolments`.
- `abacus_tools/pilots.py read --firm … --week …`; `make pilot-read FIRMS= WEEK=`.
- Tests: `tests/unit/platform/test_q04t050_wedge_read.py`,
  `tests/integration/test_q04t050_wedge_read.py` (PF-X1's two enrolments).
- DEC-1676. No migration, no flag. Rollback: revert.

## Open
- W4–W8 belong in `docs/product/discovery/thresholds.md` (F-09-T62); the read uses chapter 11's
  recommended values until they are written there.
- **Human:** the weekly read at the sprint review (`make pilot-read`) once a pilot firm, or PF-X1
  as synthetic, has snapshots for the week.

## Progress log
- 2026-11-01: built; unit 11 passed; the integration test runs at the batch's end review.
