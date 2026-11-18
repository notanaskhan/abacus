---
id: TASK-8610
title: "Q-05-T03: Contract stubs records-governance v1 and post-issuance v1"
spec: SPEC-711
acceptance_criteria: [AC-33]
risk_zone: red
status: in-review
branch: q05-t03-contract-stubs
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-18
updated: 2026-11-18
plan_key: Q-05-T03
---

## Objective
Spec section: docs/plan/epics/Q-05.md §4.3, §8.1. Pydantic models with classification tags and route stubs behind records.governance and audit.post_issuance; make generate.

## Plan (red)
1. evidence/records_governance_contract.py: 9 routes (summary, policy versions, policy create, batches, batch, documents.csv, approvals, cancel, certificate); Q-02's policy and hold routes keep their owners (their bodies extend after Oct 24, P-29).
2. assurance/post_issuance_contract.py: 5 routes (cases list, case, create, analysis, reopen for reissue).
3. Routers mounted; models prefixed Records*, PostIssuance*; api-client regenerated; tsc clean.
4. Rollback: revert; the flags stay off.

## Progress log
- `2026-11-18` — Built in the S50 sequential stack (DEC-5610). Partial: the FIL-02 and AUD-30 seed-derived fixtures come with the Q-05 seed slice (Q-05-T04). Gates and tests run once at the S50 end pass (build first, test last).
