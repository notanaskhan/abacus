---
id: TASK-3211
title: A-05-T24 contributions and remittance engine
spec: SPEC-640
acceptance_criteria: [AC-21]
risk_zone: amber
status: in-review
epic: A-05
plan_key: A-05-T24
branch: s26-a05-t24 (stacked on s26-n04-t06)
worktree: /Users/ayushkbhatia/Accrued/abacus-s26
created: 2026-11-03
updated: 2026-11-03
---

## Objective
"Dec 26 to Jan 9 is 9 business days with Jan 1 excluded, lost earnings are 64.38 with an excise
exposure of 9.66, and the waterfall foots to 1,366,900."

## Plan (amber)
- `assurance/compute/ebp/remittance.py`: `timing` (established practice; the 7-day safe harbor
  only under 100 participants), `lost_earnings` (daily compounding per quarter's §6621 rate,
  half up), `schedule_h_4a`, `waterfall`, the stamp.
- `compute/ebp/reference/irc_6621_rates.yaml`, a red file (`protected-paths.md`).
- Test: `tests/unit/assurance/test_a05t24_remittance.py`.

## Progress log
- 2026-11-03: built. I verified the figures by hand (9; 64.38; 9.66; 1,366,900). The rate file's
  `reviewed_by` stays null until the CPA memo. Tests at the S26 end review.

## Decisions made during this task
DEC-2211.
