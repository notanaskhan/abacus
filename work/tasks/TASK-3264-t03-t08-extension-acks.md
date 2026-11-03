---
id: TASK-3264
title: T-03-T08 extension acknowledgements through T-01's ack import (red)
spec: SPEC-643
acceptance_criteria: [AC-8]
risk_zone: red
status: in-review
epic: T-03
plan_key: T-03-T08
branch: s27-t03-t08
worktree: /Users/ayushkbhatia/Accrued/abacus-s27
created: 2026-11-04
updated: 2026-11-04
---

## Objective
"An imported ack file moves Feld's 4868 to Accepted and Varga's to Rejected with IND-031-04, and
the never-ERO suite proves no extension transmission path exists."

## Plan (red)
- `tax/engine_adapter.py`: the status report accepts an optional eighth column `form`; the
  seven-column report reads as before. Extension forms: 4868, 7004, 8868, 4768, IT-370.
- `tax/extension_acks.py`: in the importing unit of work, each extension row moves its
  `filing_extensions` row (return, jurisdiction, form) to accepted, or rejected with its reject
  code, audits it and emits `filing.acknowledged` with the extension and reject code (additive
  fields on `FilingAcknowledged`); an unmatched row is audited, never guessed.
- `tax/engine_files.py`: extension rows never become return acks (`engine_acks`/`efile_acks`).
- Tests: `tests/unit/tax/test_t03t08_extension_acks.py` (parser, split, no transmit path).
- Rollback: revert; seven-column reports are untouched either way.

## Progress log
- 2026-11-04: built.

## Decisions made during this task
DEC-2244.
