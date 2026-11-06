---
id: TASK-3391
title: A-06-T25 a person picks the checklist, so it can be answered
spec: SPEC-000  # row (A-06-T25)
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
epic: A-06
plan_key: A-06-T25
branch: s28q-a06-seed
worktree: /Users/ayushkbhatia/Accrued/abacus-s28
created: 2026-11-07
updated: 2026-11-07
---

## Objective
Nothing set `statement_documents.checklist_template_version_id`, so every checklist answer in any firm returned 404. Add the picker's service and routes; prove it by answering the seed's 142.

## Plan
`GET …/disclosure-checklist/templates`, `PUT …/disclosure-checklist/template`, a column grant in 0674 (still unmerged), seed: Hannah picks, Ana answers 97 Yes and 45 N/A, Hannah reviews.

## Progress log
- 2026-11-07: built. 12 passed across the completion and checklist load files (6:53; the seed's 142 answers add load time), note-template units re-run.

## Decisions made during this task
DEC-2390
