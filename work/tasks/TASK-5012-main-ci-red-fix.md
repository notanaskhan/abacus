---
id: TASK-5012
title: Main CI red since S26 fixed; audit targets placed, activity entries reviewed, CI timeouts raised
spec: SPEC-000  # row
acceptance_criteria: [AC-1, AC-2, AC-3]
risk_zone: amber
status: in-review
epic: Q-03
plan_key: Q-03-T172
branch: main-red-fix
worktree: /Users/ayushkbhatia/Accrued/abacus-s26
created: 2026-11-05
updated: 2026-11-05
---

# TASK-5012 · Main CI red since S26

AC-1: every test that failed on main's CI runs a369a01fa, 596eba9cd and ab2cef04c passes, and no
assertion was dropped or weakened to get there.

AC-2: every audit target type the code records has an owner or is firm-level, and every audited
action has a catalogue entry or a reviewed fallback.

AC-3: stage 1, the unit shards and the integration shards finish inside their job limits.

## What was wrong (DEC-2264)
- **Product gaps.** Eight target types had no owner, so the audit explorer hid their events:
  `control_activity`, `control_exception`, `deficiency`, `sum_snapshot`, `notice`, `notice_intake`,
  `ocr_run`, `questionnaire`. 38 audited actions had no reviewed entry. `TestGridRowOut.state` was
  an untyped string. Five stub routes that create rows answered 200.
- **Tests that had not followed reviewed changes.** Pinned lists (routes, independence marks,
  compute packages, notifications, worker handlers, immutable tables); the flag-off tests for
  `review.grammar_api`, retired by DEC-2221; the C11 action test, which also read the statements
  stub's routes; the notices gate test, whose stub resource was not a dataclass and whose route
  went live in N-04-T11; the reporting insert-only test, which named one trigger function.
- **A harness gap.** The review and planning loaded tests reached the dev S3 gateway on 7070, which
  exists on a laptop and not on CI. They now take the `object_store` fixture.
- **Job limits.** Stage 1 (15 min), a unit shard (25) and three integration shards (60) were
  cancelled at their limits, hiding any failure behind them.

## Known limits
An intake with no client yet, and a firm template's questionnaire, have no owner and stay hidden
from the explorer (fail closed). The events remain in the audit chain.

## Progress log
- 2026-11-05: built on main ab2cef04c; see the PR for the test evidence.
