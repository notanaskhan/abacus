---
id: TASK-3316
title: "A-07-T12 template content part 1: letters by import, checklists as content"
spec: SPEC-000  # row (A-07-T12)
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
epic: A-07
plan_key: A-07-T12
branch: s28-a07-t12
worktree: /Users/ayushkbhatia/Accrued/abacus-s28
created: 2026-11-05
updated: 2026-11-05
---

## Objective
"make seed-demo loads every template through the import endpoints, the licensed-text detector reports zero hits, and no template wording appears in Python or TypeScript sources."

## Plan
- `files/a07_templates.yaml`: EQR 10, completion EBP 18 and FS variant, archive 9, letters.
- Slice `a07_templates` through `reporting.template_imported`/`published`.
- Rollback: drop the slice; nothing else reads it.

## Progress log
- 2026-11-05: built. Tests at the S28 end review.

## Decisions made during this task
DEC-2315
