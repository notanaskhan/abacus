---
id: TASK-2136
title: Q-03-T090 Source-assisted review of A-01's export create and download
spec: SPEC-000  # Q-03-T090 row; SPEC-344 is the reviewed spec
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: red
status: in-review
epic: Q-03
plan_key: Q-03-T090
branch: s16-q03-t090
created: 2026-10-29
updated: 2026-10-29
---

## Objective
A non-author, source-assisted review of A-01's export create and download before M9; findings fixed
before any real firm exports.

Acceptance (backlog row): "The review record lists every route and check, and no real-firm export
is enabled while a finding is open."

## Progress log
- 2026-10-29: record `docs/quality/reviews/2026-10-29-a01-export.md`: five routes and their checks
  with the tests behind them; the 2026-10-27 fixes confirmed; one low finding open (R-01: the
  two-stream cap is per API process), two informational. Real-firm export stays off until R-01 is
  fixed or accepted (human decision; A-01 is N's epic).
