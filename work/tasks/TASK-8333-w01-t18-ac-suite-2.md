---
id: TASK-8333
title: "W-01-T18: ADR-078 AC suite 2 for the red Connect work"
spec: SPEC-659
acceptance_criteria: [AC-13, AC-14, AC-15, AC-16, AC-27, AC-28, AC-29, AC-30]
risk_zone: red
status: in-review
branch: w01-t18-ac-suite-2
worktree: /Users/ayushkbhatia/Accrued/abacus-s47g04
created: 2026-11-16
updated: 2026-11-16
plan_key: W-01-T18
---

## Objective
Spec section: docs/plan/epics/W-01.md F4, F5.
ADR-078 AC suite 2 for the red Connect work.

## Plan (red)
1. `tests/unit/integrations/test_w01t18_ac_suite_2.py` (`ac-test-author: ayushkbhatia`): AC-13 every (status, probe) pair, AC-14 the needs-attention threshold, AC-15 admission across every status, AC-16 one event per change over a scripted sequence.

## Progress log
- `2026-11-16` — Built in the S47 sequential stack. The file ran green (39 cases). Partial: AC-27 to AC-30 (membership-end revocation, client-company walls, fake-adapter refusal, retention registration) need W-01-T15's projection and Postgres; written at the end pass. Gates and
  tests run once at the S47 end pass (build first, test last).
