---
id: TASK-1855
title: Q-03-T059 re-run the 44 back-filled suites against the final MVP contracts
spec: SPEC-045
acceptance_criteria: [AC-2]
risk_zone: red
status: in-review
epic: Q-03
branch: s12r-q03-t059
created: 2026-10-28
updated: 2026-10-28
---

## Objective
All 44 suites are green on main or each failure has a defect ticket with an owner.

## Built
- `abacus_tools/quality/backfill_rerun.py` and `make backfill-rerun`: the 44 rows of
  `docs/quality/backfill.md` resolved to their suites (a tranche-0 row naming none runs every
  backend test citing its SPEC), one pytest and per-file vitest runs, the report
  `docs/quality/backfill-rerun-<date>.md`.
- `tests/unit/tools/test_backfill_rerun.py`.

## Found while planning
- TASK-059 AC-10's suite `legacy/spec030review.test.tsx` was deleted with the legacy screens
  (#464, S10 wave C); the re-run reports it missing. Triage at the run.

## Open
- The run itself and its triage: at the end review (session rule), defects into
  `escaped-defects.md`.

## Progress log
- 2026-10-28: tool built; run pending.
