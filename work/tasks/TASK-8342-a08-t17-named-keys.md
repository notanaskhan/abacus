---
id: TASK-8342
title: "A-08-T17: Sample expansion, the rest: named keys (Add participants) and the approver's notification"
spec: SPEC-657
acceptance_criteria: [AC-3]
risk_zone: amber
status: in-review
branch: a08-t17-named-keys
worktree: /Users/ayushkbhatia/Accrued/abacus-s47g04
created: 2026-11-16
updated: 2026-11-16
plan_key: A-08-T17
---

## Objective
Spec section: SPEC-657 F3 (AC-3.4); A-08 §4.7. Sample expansion, the rest: named keys (Add participants) and the approver's notification.

## Plan (amber)
1. Named keys append last with selection reason `named`, each in the population and not yet selected (422 `expansion_key_invalid`); 0931 adds `named` to `sample_items.selection_reason`.
2. `sample_expansion.requested` carries the approver and requester; C16 kind `sample_expansion_approval_requested` tells the named approver, never the requester.

## Progress log
- `2026-11-16` — Built in the S47 sequential stack (DEC-5327). Lint, pyright clean; the app imports; client regenerated. Gates and
  tests run once at the S47 end pass (build first, test last).
