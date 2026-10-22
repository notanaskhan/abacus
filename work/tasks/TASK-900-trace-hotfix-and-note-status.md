---
id: TASK-900
title: "Hotfix TASK-461's two main failures; make reviewable_notes.status authoritative"
spec: SPEC-318
acceptance_criteria: [AC-3]
risk_zone: amber
status: done
branch: task-462-trace-hotfix
worktree: agentwt
created: 2026-10-22
updated: 2026-10-22
---

## Plan
- **Trace hotfix:**
  - classify `RunTraceOut.run`, `rows`, `records_read` and `output_counts` (`test_ac20_every_abacus_model_field_is_classified`);
  - drop the unused `"info"` trace-row state, which isn't in the status vocabulary (`test_f03_status_vocabulary`).
- **Note status:**
  - `review/notes.py` writes `reviewable_notes.status` in the same unit of work as each event: raised → open, responded, cleared, reopened → open, closed, withdrawn. Migration 0093 and ADR-160 clause 6 make that column authoritative.
  - Raising now also records a `raised` event, whose body is the note text because migration 0076's CHECK requires one.
  - Reads use the column. The note row is locked (`FOR UPDATE`) for each change.
  - The API status is widened to C3's closed and withdrawn.
- **Rollback:** revert the PR. There are no migrations.

## Notes
- Task numbers 900 and up are reserved for this stream so they stay clear of the other stream's sequence, which is past TASK-422.
- I made a mistake in TASK-461: I didn't run the classification or status-vocabulary tests before merging. When adding response models or status Literals, run `tests/unit/kernel/test_classification.py` and `tests/acceptance/test_f03_status_vocabulary.py`.

- I also fixed three things on main that blocked check-fast:
  - a pyright `cast` in `test_review_status_registry.py`;
  - secrets-scan ALLOW entries for the C3 `field_key` tax-line codes, which are false positives;
  - Prettier formatting on `packages/ui/src/tokens/DECISIONS.md`.

## Progress log
- Dev smoke test on one note:
  - raised gives open, with a raised event;
  - responded gives responded;
  - cleared gives cleared;
  - reopened gives open;
  - cleared again gives cleared.
  - The view hides the raised event.

## Definition of done
- [x] Classification, status vocabulary, review, api, independence, route introspection, C3 contract and schema-check tests pass.
- [x] spec313review and spec318runs pass; web tsc is clean.
- [x] make check-fast passes in full.
