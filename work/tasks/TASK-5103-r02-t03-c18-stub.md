---
id: TASK-5103
title: R-02-T03 C18 portal approvals contract stub
spec: SPEC-000  # row (R-02-T03)
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
epic: R-02
plan_key: R-02-T03
branch: s29-r02-t03
worktree: /Users/ayushkbhatia/Accrued/abacus-s29
created: 2026-11-06
updated: 2026-11-06
---

## Objective
C18 as a contract: the fail-closed slot, DTOs, decider table and approval routes.

## Plan
engagements/client_approvals.py; portal/approvals_contract.py; portal.yaml rows; docs/contracts/portal-approvals.md; regenerate. Corrects the POR contracts' screen task numbers (POR-09 T17, POR-15 T21). Rollback: revert, nothing live.

## Progress log
- 2026-11-06: built. `backend/tests/contracts/c18_portal_approvals/test_c18_stub.py` written, not run (end pass).

## Decisions made during this task
DEC-2403
