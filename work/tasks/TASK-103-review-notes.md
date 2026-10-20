---
id: TASK-103
title: "SPEC-041: review notes on fieldwork rows and workpapers — raise, respond, clear; open notes block reviewer sign-off; drawer thread; Home queue entries"
spec: SPEC-041
acceptance_criteria: [AC-1, AC-2, AC-3, AC-4, AC-5, AC-6, AC-7, AC-8]
risk_zone: red
status: done
branch: spec-041-review-notes
worktree: spec005
created: 2026-10-20
updated: 2026-10-20
---

## Plan
1. Migration 0062: `review_notes` and `review_note_events`, insert-only with RLS forced; `schema_check` entries.
2. Matrix: `review_note.raise`, `.respond`, `.clear`.
3. `fieldwork/notes.py`: raise, respond, clear, list with derived state, `open_notes` for the gates. `flow.sign_items` (reviewed) and `workpapers.sign_reviewed` gated on them. `waiting_for` adds respond and clear entries.
4. Routes:
   - `GET /procedures/{id}/notes`;
   - `POST /procedures/{id}/notes`;
   - `POST /procedures/{id}/notes/{note_id}/respond`;
   - `POST /procedures/{id}/notes/{note_id}/clear`.
5. Web: a notes drawer per row and per workpaper, a note count on rows, and Home queue wording.

Approved by founder (2026-10-20, "approved, proceed"). Approval file: `work/approvals/TASK-103.yaml`.

## Definition of done
- [x] `test_notes.py` (6), `spec041notes.test.tsx` (4); the fieldwork, flow and Home screen tests pass; `make check-fast` passes.
- [ ] Not walked live (the dev server was stopped); owed: ADR-078 integration tests for raise / respond / clear and the two gates.

## Gotchas
- `not_note_raiser` is a 409 conflict (as ADR-131's `reviewer_is_preparer` is), not a 403; SPEC-041 says so.
