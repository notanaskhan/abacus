---
id: TASK-1733
title: P-04-T33 Independent AC tests for Undo and the effect hold
spec: P-04 §9 (T33); DEC-713
acceptance_criteria: [P-04-T33]
risk_zone: red
status: in-review
epic: P-04
plan_key: P-04-T33
branch: s14-p04-t33
created: 2026-10-28
updated: 2026-10-28
---

## Objective
ADR-078 independent tests for P-04-T29. Acceptance (backlog row): "Tests written in
ayushkbhatia's session pass and fail if an external effect fires before not_before."

## Plan (red, tests only)
- `backend/tests/integration/backfill/test_p04t33_undo_effect_hold_independent.py` on P-04-T28's
  world: decision at once, Undo writes `undone`, second Undo refused, grant hold before
  `not_before`, void on Undo, no void after consume, payload binding. DEC-823 (Temporal replay
  has nothing to replay yet).

## Progress log
- `2026-10-28` — Written. ruff and pyright clean. Not run (end-of-batch review).

## Handoff
- **Current state:** PR open, held for the batch.
- **Next:** Q-04-T013.
