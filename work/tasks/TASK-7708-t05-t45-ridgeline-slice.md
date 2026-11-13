---
id: TASK-7708
title: T-05-T45 Brightwater Hale Ridgeline slice part 1 through service APIs
plan_key: T-05-T45
spec: SPEC-651
acceptance_criteria: [AC-F14]  # the Ridgeline and Harborview slice loads on synthetic firms only
risk_zone: amber
status: in-review
branch: t05-t45-ridgeline-slice
worktree: /Users/ayushkbhatia/Accrued/abacus-s41
created: 2026-11-13
updated: 2026-11-13
---

## Objective
`make seed-demo` with `--slice entity` puts Ridgeline and Harborview in the database through
service APIs at their clocks: facts, cells, the allocation structures and their sign-offs, and
Runs 1 and 2.

## Plan (amber)
- Files: `tax/entity_seed.py` (synthetic-only recorder), `tax/api.py` exports,
  `tax/allocation_structure.py` (`approve(rerun=...)`), `abacus_tools/.../entity_slice.py`,
  `loader.py` (four handlers in dependency order).
- No migration, matrix or flag definitions (the slice sets the three T-05 flags for the
  synthetic firm).
- Tests: `backend/tests/unit/tax/test_t05t45_entity_slice.py`; the full load in the end pass
  (`make seed-demo` with the slice, then TXP-00 A/D/E and TXP-06 B read from the database).
- Rollback: revert; the slice is opt-in.

## Partial
- The LPA and assignment documents with word layers, and the reader's adoption with two bbox
  clause citations (carried from T-05-T36/T41): not loaded; Ridgeline's structure is a person's
  draft (DEC-4711). T-05-T62 (slice part 2) takes the documents and the reader run.
- The 28-account TB is written as workbook cells, not as a C9 trial balance version with the
  AJE through C8: TXP-02 reads the ledger's TB (T-05-T33), so the TB screen's live read still
  needs the ledger slice (T-05-T62).
- Run 2's 11 open items: the issues come from the existing Ridgeline issues slice
  (`review.ridgeline_issue_created`); the run's items list is not recorded.
- Engagement roles: the drafts assume Daniel Reyes is a manager or partner on both engagements
  and Samuel Ito may sign L3; the end-pass load verifies it.

## Progress log
- 2026-11-13: built; slice smoke-imported (13 events, 264 cells; TB foots to 0); tests written,
  not run.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-4711 | the slice's service paths and deviations | no |
