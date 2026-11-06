---
id: TASK-3390
title: A-06-T25 the statements' note templates, firm content drafted into each version
spec: SPEC-000  # row (A-06-T25)
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
epic: A-06
plan_key: A-06-T25
branch: s28q-a06-notes
worktree: /Users/ayushkbhatia/Accrued/abacus-s28
created: 2026-11-07
updated: 2026-11-07
---

## Objective
Close DEC-2304's and DEC-2380's last open piece: `note_ref` was always empty and a statement version had no notes, because no note-template model existed.

## Plan
Migration 0674 on 0673: `statement_note_templates`, `statement_note_template_versions` (methodology, firm content), `statement_notes` (reporting, insert-only). Import and publish routes as the checklist's, matrix, generated client. `_draft` reads the framework's latest published version, sets `note_ref`, renders notes with figures from the version's own lines. Rollback: drop the three tables; a version with no notes reads as before.

## Progress log
- 2026-11-07: built. 27 passed: the completion and checklist load files, statements engines and jobs, migration test; 5 new unit tests. Gates at the end of the round.

## Decisions made during this task
DEC-2389
