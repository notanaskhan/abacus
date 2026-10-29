---
id: TASK-2013
title: Q-03-T088 ADR-078 catch-up lane 2027 Q2, part 1
spec: SPEC-341
acceptance_criteria: [AC-48]
risk_zone: red
status: in-review
epic: Q-03
plan_key: Q-03-T088
branch: s15n-q03-t088
created: 2026-10-29
updated: 2026-10-29
---

## Objective
Independent AC tests (ADR-078) for N's quality tooling, from chapter 10 and the rows only: the
weekly report (T003), red-module coverage floors (T066), mutation wiring (T026) and its protected
floors (T027).

## Result
`backend/tests/unit/quality/test_q03t088_independent.py`, ran once: 9 passed, 1 strict xfail.
- T003: every §10.14.2 area publishes with no inputs and nothing written in the repository; the
  workflow commits, pushes and deploys nothing and reads contents only.
- T026: mutmut is cut at 60 minutes nightly and 230 minutes a weekly shard (inside 4 hours); the
  nightly plan takes only changed red files.
- T027: a lowered floor and a dropped scope are refused; a raised floor passes.
- **T066 is not built**: no per-red-module floor fails stage 2. The AC test is a strict xfail citing
  this task; the weekly report still names a red module under 97% (passing test). Q-03-T066 needs
  building (S13 row, not in this block).

## Remaining time
No other epic's deferred red or amber suite was found in this block's window beyond T066.
