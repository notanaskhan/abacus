---
id: TASK-7701
title: T-05-T41 Allocation structure service (GET, PUT draft, POST preview, L3 approval and re-run, proposal adoption)
plan_key: T-05-T41
spec: SPEC-651
acceptance_criteria: [AC-5.1, AC-5.2, AC-5.3, AC-5.4]  # T-05 F5
risk_zone: amber
status: in-review
branch: t05-t41-allocation-structure
worktree: /Users/ayushkbhatia/Accrued/abacus-s41
created: 2026-11-13
updated: 2026-11-13
---

## Objective
TXP-06's backend: the allocation structure's versions, a manager's draft and preview, the
agreement reader's proposal adopted as Pending approval, and Samuel's L3 sign-off that approves the
structure and re-runs the capital and K-1 groups, with agent and staff approvals refused.

## Plan (amber)
- Files: `backend/src/abacus/modules/tax/allocation_structure.py` (new: pure draft, hash and
  compute over E5 parts 1 and 2; reads; `save_draft`, `preview`, `approve`, `adopt_proposal`;
  reviewable and facts; `register()`), `tax/workbook_contract.py` (the three stubs answer, new
  `POST …/allocation-structure/approve`, additive response and request fields), `tax/api.py`
  (registration at import), `tax/audit_targets.py` (`allocation_structure` audit kind),
  `audit_trail/activity_reviewed.py` (three reviewed actions), `docs/contracts/tax-workbook.md`.
- Migrations: none (0821's tables; insert-only and the human-only approved CHECK hold).
- Registry and flags: none new; `tax.entity_workspace` gates every route; matrix rows exist
  (T-05-T04). Reviewable `allocation_structure` and its facts; proposal adapter
  `allocation_structure` (the kind T-05-T36's tool writes).
- Tests: `backend/tests/unit/tax/test_t05t41_allocation_structure.py`.
- Rollback: revert the PR; the routes answer 501 again and no table changes.

## Built
- Ridgeline's 628,100 × 2 under monthly interim closing (Meera Shah 238,678 in period 1, Pell
  Street II nothing), Harborview's 4,000,000 + 312,000 + 78,000 + 510,000 = 4,900,000 with plugs
  of 900,000, computed and stored per partner, period and rung.
- Version conflict 409, editor role 403 (manager or engagement partner), preview with no write.
- Approval: P-04's `sign_target` at L3 refuses an agent (R-SO-1), staff (`level_not_permitted`)
  and the version's preparer (R-SO-3, DEC-4702); the person's own `approved` version follows,
  then a `group` run of `capital` and `k1s` (skipped while a run is open; the answer says so with
  no run id).
- The proposal adapter adopts an approved `allocation_structure` proposal as Pending approval.

## Partial
- SHL-08's lit clause: the reader's clause citations reach the structure's `citation_ids` when the
  proposal rows carry them, but clause segmentation of the LPA's text layer and `document_text`
  citation rows with a bbox (carried from T-05-T36) are not built: the reader is still handed
  clause ids and text by its caller. Carried to T-05-T45 (the Ridgeline slice loads the LPA and
  assignment with word layers) and recorded there.
- An L3 signed directly through `POST /v1/sign-offs` (not TXP-06's approve route) counts as the
  sign-off but writes no approved version and starts no re-run; TXP-06 uses the approve route.
- The integration-level AC (real services, Samuel's L3 and the run row) is T-05-T56's
  independent suite (ADR-078) and T-05-T67's journey; here the rules are unit-tested with P-04
  stubbed.

## Progress log
- 2026-11-13: plan, service, routes, registrations, contract notes, unit tests written (not run:
  tests run at the S41 end pass). OpenAPI export lists the four allocation-structure routes.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-4701 | the service shape and the tax-owned approve route that keeps the person's context for the re-run | no |
| DEC-4702 | the drafter or adopter prepares a version; another manager or partner approves | no |
