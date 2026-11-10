---
id: TASK-6403
title: N-04-T07 follow-ups - Create anyway names its reason, Attach files the document, no ten-minute wait
spec: SPEC-000  # row
acceptance_criteria: [AC-1, AC-2, AC-3]
risk_zone: amber
status: in-review
epic: N-04
plan_key: N-04-T07
branch: s26p-n04-t07-intake2
worktree: /Users/ayushkbhatia/Accrued/abacus-s26
created: 2026-11-08
updated: 2026-11-08
---

# TASK-6403 · N-04-T07: Create anyway names its reason, Attach files the document, no wait

TASK-5013 left Create anyway without a reason, Attach without filing the document on the chosen notice, and a file read before its intake waiting ten minutes. Functions at Create notice (DEC-2392) and the responder's extract mode (N-04-T19) landed since.

AC-1: Create anyway past a possible duplicate needs a reason (different notice, different tax year, reissued by the agency, something else) and records it on the intake; without one it is 422 `create_anyway_reason_required`.

AC-2: Attach to N2 files the intake's document on N2 as a new item pointing at the same stored bytes; the original stays where it was.

AC-3: A file whose text was ready before its intake (a text layer or a completed OCR run) is read at once, not after ten minutes.

## Decisions (DEC-2953)
- Migration 0740 adds `notice_intakes.create_anyway_reason_code` (expand-only, a code like the discard reason's).
- Evidence placement is set once, so Attach files a new item whose first version points at the same content-addressed bytes (`evidence.api.file_copy_onto_work_item`).
- NOT-01's "Create anyway…" is a menu of the four reasons.
- Not built: matching on the taxpayer's name in code. A CP14 carries no labelled name line (the synthetic corpus shows none), so a form map has nothing to anchor; names come from the responder's extract mode or the person's client pick.

## Known limits
- Code's client match stays on the last four: no notice form has a labelled name to map.

## Progress log
- 2026-11-08: built on main a801fff01; tests written, run at the S26 partials end pass.
