---
id: TASK-2322
title: T-02-T13 return overview read model and record projection
spec: SPEC-502
acceptance_criteria: []
risk_zone: amber
status: in-review
epic: T-02
plan_key: T-02-T13
branch: s18-t02-t13
worktree: /Users/ayushkbhatia/Accrued/abacus-s18
created: 2026-10-30
updated: 2026-10-30
---

## Objective
TAX-02's record and overview read model (ladder from C3 sign-offs, pipeline, Filing band with the
C19 consent summary, engine summary from approved imports only, allowed actions), the two
requestable transitions, and the record projection's subscribers.

## Plan
- `tax/overview.py`; `board.ReturnRow`/`row_out`; record, overview and transition routes live;
  `binder.published` and `sign_off.recorded` subscriptions.
- Overview route declares `tax_return.read_metadata` (route introspection and stub tests updated).
- Tests: `tests/unit/tax/test_t02t13_overview.py`, `tests/integration/test_t02t13_return_overview.py`.
- DEC-1368. Rollback: revert.

## Progress log
- `2026-10-30` — built (DEC-1368); unit (5) and contract (11) tests run once; integration in the S18
  end review. `[skip ci]`.

## Handoff
- **Current state:** built, PR open, held for the S18 batch.
- **Exact next step:** T-02-T16 questionnaire engine.
