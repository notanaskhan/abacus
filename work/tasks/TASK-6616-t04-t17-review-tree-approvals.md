---
id: TASK-6616
title: "T-04-T17: Review tree and document approvals, final-approval request with blockers, workspace summary"
spec: SPEC-649
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
branch: s34-t04-t17
worktree: /Users/ayushkbhatia/Accrued/abacus-s34
created: 2026-11-10
updated: 2026-11-10
plan_key: T-04-T17
---

## Objective
Samuel's tree shows Review 37 for 41 documents and 36 after one approval, Kevin cannot approve at
manager level, and a final-approval request with a Draft K-1 answers 409 with blocker draft_k1.

## Plan (amber)
1. `tax/review_tree.py` (new): levels from work-item functions; the tree (current versions,
   approval at the level, "Review n", `q` and category); approve (level held, current version,
   insert-only, a person's) and reverse (own level, once, sealed reason); final-approval request
   with blockers `draft_k1`, `unapproved_documents`; the workspace summary.
2. `evidence.api.engagement_documents`; `engagements.api.functions_on` exported.
3. Routes live: workspace, review-tree, document-approvals, reverse, final-approval-requests.
4. Tests: `tests/unit/tax/test_t04t17_review_tree.py`.

## Progress log
- `2026-11-10` — Built; ruff, pyright clean; the app imports. Tests not run (end pass). Partial:
  the code mismatch check (409 `mismatch` with an issue suggestion), the leadsheets, the Sch E K-1
  matrix with the PY column and the region-field-line links stay 501 (they need the engine's
  document-to-field map, T-04-T21); `issues_open` reads 0 and `assistant` reads `agents_off`
  until the issues read and TAX-08 land; the request writes its audit event for the gate
  projection rather than a C13 gate row.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-3210 | Level mapping, version check, blockers | no |
