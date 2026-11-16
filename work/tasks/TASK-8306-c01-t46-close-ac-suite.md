---
id: TASK-8306
title: "C-01-T46: Independent AC tests (ADR-078) for the close record, plan, intake and run services"
spec: SPEC-655
acceptance_criteria: [AC-9, AC-13, AC-18, AC-24]
risk_zone: amber
status: in-review
branch: c01-t46-close-ac-suite
worktree: /Users/ayushkbhatia/Accrued/abacus-s47g04
created: 2026-11-16
updated: 2026-11-16
plan_key: C-01-T46
---

## Objective
Spec section: docs/specs/SPEC-655-c01-close-engine-v1.md §4 F1 to F4.
Independent AC tests (ADR-078) for the close record, plan, intake and run services.

## Plan (amber)
1. `tests/integration/test_c01t46_close_ac_suite.py` (`ac-test-author: notanaskhan`): INV-1 refusals (status, run start, publish, adopt) with the refusal kept and attributed to the agent; AC-18 pinned close never changes plan version; AC-13 twelve closes and 409 on a thirteenth; AC-9 In review gate names the missing account; INV-3 a close outside the team is 404 and uncounted; AC-24 strict xfail while C-01-T19's intake summary answers 501.

## Progress log
- `2026-11-16` — Built in the S47 sequential stack. Lint and pyright clean; runs at the end pass under the test lock. Gates and
  tests run once at the S47 end pass (build first, test last).
