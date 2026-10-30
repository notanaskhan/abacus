---
id: TASK-2311
title: K-02-T12 reference-set publication fan-out
spec: SPEC-500
acceptance_criteria: [AC-49, AC-50, AC-51]
risk_zone: amber
status: in-review
epic: K-02
plan_key: K-02-T12
branch: s18-k02-t12
worktree: /Users/ayushkbhatia/Accrued/abacus-s18
created: 2026-10-30
updated: 2026-10-30
---

## Objective
Temporal fan-out writing one reference_set.published audit and outbox event per active tenant
with the operator and approver handles, plus the C16 "Rules table updated" kind. Acceptance
(row): one publish yields exactly one audit event and one notification set per active tenant,
and a re-run is idempotent on tenant and version.

## Plan
- Stacked on #822 (K-02-T06, the CLI that starts it).
- `platform/reference_fanout.py`, `platform/reference_fanout_workflow.py`; platform WORKFLOWS and
  ACTIVITIES; CLI `fanout`; notifications catalogue kind and template.
- Tests: `tests/unit/platform/test_k02t12_reference_fanout.py`; replay history at the end review.
- Rollback: revert.

## Progress log
- `2026-10-30` — built (DEC-1358). Tests written, not yet run (S18 end review; `[skip ci]`).

## Handoff
- **Current state:** built, PR open, held (after #822).
- **Exact next step:** K-02-T14 KNW-04i frontend.
