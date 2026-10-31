---
id: TASK-2811
title: A-05-T05 protected bundle (glossary, status vocabulary, human-only acts)
spec: SPEC-640
acceptance_criteria: [AC-1]
risk_zone: red
status: in-review
epic: A-05
plan_key: A-05-T05
branch: s23-a05-t05 (stacked on s23-a05-t04)
worktree: /Users/ayushkbhatia/Accrued/abacus-s23
created: 2026-11-01
updated: 2026-11-01
---

## Objective
- **[AC-1]** "Generated allow and deny tests prove agents are refused verify, adopt, record
  correction, evaluate certification and conclude, and make check-fast passes with the three
  flags off."

## Plan (red)
- Matrix rows and flags: in A-05-T04 (the router needs them; DEC-1859); generated suites there.
- Here: glossary rows, eight status objects (+ codegen), a security test naming the five acts.
- TABLE_OWNERS with the T06 migration (schema-checked). Rollback: revert.

## Progress log
- `2026-11-01` — built; status codegen run. Tests and `make check-fast` at the S23 end review.

## Decisions made during this task
DEC-1860.
