---
id: TASK-6614
title: "T-04-T15: Review registrations from the tax module: reviewables, field owner with TRI tagging, suggestion targets and proposal appliers"
spec: SPEC-649
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
branch: s34-t04-t15
worktree: /Users/ayushkbhatia/Accrued/abacus-s34
created: 2026-11-10
updated: 2026-11-10
plan_key: T-04-T15
---

## Objective
Unregistered targets stay refused, a field edit through PUT /v1/fields/return_worksheet/... writes
one field_value_versions row and moves the section hash, and the section's sign-off reads stale.

## Plan (amber)
1. `tax/worksheet_review.py` (new): reviewables and facts for `return_worksheet` and
   `return_worksheet_section` (content hash over the fields' keys and values); the field owner
   (value, label, TRI on every key, a person's edit that refuses engine fields, rehashes the
   section and the worksheet, checkpoints); suggestion targets `return_field`,
   `pass_through_treatment`, `residency_determination`; proposal appliers that write only an
   approved proposal's rows (`record_value` for fields; K-1 and residency rows link the proposal
   for the person's own confirm).
2. `agents.api.approved_proposal_rows`; `tax.audit_targets` owns `return_worksheet`; reviewed
   audit actions.
3. Tests: `tests/unit/tax/test_t04t15_review_registrations.py`.

## Progress log
- `2026-11-10` — Built; ruff, pyright clean; the app imports. Tests not run (end pass). Partial:
  derived-line recompute after an edit is T-04-T16's applier; K-1 and residency appliers link the
  proposal and leave the confirm to the person (T-04-T17 and the TAX screens). The slots' codes
  hold no digits, so the K-1 target is `pass_through_treatment`.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-3208 | Hash basis, TRI tagging, engine fields read-only, K-1 code name | no |
