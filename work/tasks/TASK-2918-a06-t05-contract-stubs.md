---
id: TASK-2918
title: A-06-T05 C8 and completion contract stubs
spec: SPEC-642
acceptance_criteria: [AC-3]
risk_zone: red
status: in-review
epic: A-06
plan_key: A-06-T05
branch: s24-a06-t05 (stacked on s24-a06-t04)
worktree: /Users/ayushkbhatia/Accrued/abacus-s24
created: 2026-11-01
updated: 2026-11-01
---

## Objective

One stub per screen family: C8 (proposed entries, approval batches, adjusted TB) and completion (findings, misstatements, SUM, snapshots), answering 501 until their tasks.

## Plan

- `adjustments/contract.py` (router mounted from `adjustments.api.ROUTERS`; `adjustments.entries`) and `assurance/findings_contract.py` (mounted from `assurance.api.ROUTERS`; `assurance.completion`): client 404, the action on the work item's engagement, flag 404, 501.
- Matrix: `finding.*`, `misstatement.*`, `sum.*`, `consultation.*` in `assurance.yaml`; a new `adjustments.yaml` with `proposed_entry.*`, `approval_batch.create`, `adjusted_tb.read` (agent deny on every write; task-scope reads); `_matrix.py` and `actions.gen.ts` regenerated.
- Flags: `assurance.completion`, `adjustments.entries` (`_flags.py` regenerated).
- Contracts `docs/contracts/adjustments.md` (C8, v1 freeze Fri Oct 1, 2027) and `docs/contracts/completion.md`; the register's C8 row reads stub.
- `make generate` (the OpenAPI client) runs in the end review.

## Progress log

- 2026-11-01: built in abacus-s24, stacked on A-06-T04.
