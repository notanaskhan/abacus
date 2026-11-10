---
id: TASK-6717
title: "T-04-T24: independent AC tests (ADR-078) for the individual workspace migration, registrations, worksheets and approvals"
spec: SPEC-649
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
branch: s35-t04-t24
worktree: /Users/ayushkbhatia/Accrued/abacus-s35
created: 2026-11-10
updated: 2026-11-10
plan_key: T-04-T24
---

## Objective
A second tenant reads nothing, the agent principal is refused every approval and edit, Review counts match 37 and 36 for Samuel, and every new model field carries a classification tag.

## Plan
`backend/tests/integration/test_t04t24_individual_workspace_independent.py` (ADR-078 solo
independence, DEC-3127): forced RLS and the tenant policy on all nine 0761 tables, an empty read for
another tenant through the app role, insert-only grants, the human-only and reversal constraints on
`document_approvals`, and classification tags on every workspace and worksheet contract field
(values Confidential or Restricted).

## Partial
- The service-level checks the row names (Review 37 → 36 for Samuel, reason-required edits,
  `expected_version` conflicts, stale sign-offs, the agent refused at the service) are covered by
  T-04-T15/T16/T17's own suites; an independent HTTP-level suite over a seeded Feld return is left
  for T-04-T23's integration fixtures.

## Progress log
- `2026-11-10` — Written; run at the end pass.
