---
id: TASK-3394
title: A-06-T24 AUD-17 Reopen and the changed-paper notice
spec: SPEC-000  # row (A-06-T24)
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
epic: A-06
plan_key: A-06-T24
branch: s28p-a06-t24
worktree: /Users/ayushkbhatia/Accrued/abacus-s28
created: 2026-11-08
updated: 2026-11-08
---

## Objective
DEC-2318 left Reopen and the thread's stale notice waiting on the server: `allowed_actions` never offered a reopen, and the detail had no fact for a paper changed after a sign-off.

## Plan
- `review/notes.py`: `_allowed` adds `review_note.reopen` on a cleared note for the raiser or the engagement partner; the detail carries `paper_changed_after_signoff` from the note's reviewable hash and its sign-off states.
- C3 `POST /v1/review-notes/{note_id}/reopen` (`review_note.clear`, body required), contract doc, regenerated client.
- AUD-17: secondary Reopen opens the composer and Send reopens with why; the amber notice uses the handoff's copy.
- Rollback: revert; no migration.

## Progress log
- 2026-11-08: built. `tests/unit/review/test_a06t24_note_reopen.py` (8), `AUD-17.test.tsx` (2 new, 11 pass in the folder); ruff, pyright, eslint, tsc clean on the touched files.

## Decisions made during this task
DEC-2393
