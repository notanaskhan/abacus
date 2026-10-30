---
id: TASK-2314
title: T-01-T18 final-approval guard
spec: SPEC-501
acceptance_criteria: [AC-45, AC-46, AC-47, AC-48, AC-49, AC-50]
risk_zone: red
status: in-review
epic: T-01
plan_key: T-01-T18
branch: s18-t01-t18
worktree: /Users/ayushkbhatia/Accrued/abacus-s18
created: 2026-10-30
updated: 2026-10-30
---

## Objective
`tax/approval.py`, the single owner of a tax return's L4 `final_approval` sign-off (absorbs the
former T-02-T15): BH-TAX-02's signer, eligibility with every blocker, five-layer human-only
approve writing the sign-off, the `approved` status, one export grant (`not_before` + 10 s) and
`tax_return.approved` in one unit of work; the return's reviewable facts and gate kind
`tax_final_approval`.

## Plan
- `review.api`: `current_checkpoint`, `pending_imports`, `blocking_issues` (reads for the guard).
- `methodology.api`: `policy_payload`, `ReturnApprovalPolicyPayload` export.
- `tax/approval.py`: signer, `eligibility`, `approve`, blocker slot, `register()` (facts + gate).
- `tax/engine_contract.py`: the two final-approval routes live behind `tax.engine_bridge`; the
  `final_approval_blockers` stubs removed (`tax.api.final_approval_eligibility` instead).
- `tax/repository.py`: `statuses_on` for the gate.
- Error catalogue (`final_approval_blocked`), generated client, SPEC-501 AC-45 to AC-50,
  DEC-1360.
- Tests: `tests/unit/tax/test_t01t18_final_approval.py`; engine stub contract test splits LIVE.
- Rollback: revert; no migration.

## Progress log
- `2026-10-30` — built (DEC-1360). Unit test and the two stub contract tests run once (65 pass);
  integration (a real L4 row, the grant, the gate) waits for T-01-T31 and the S18 end review.
  `[skip ci]`. Stacked on K-02-T10 (#823) for `return_approval_policy`.

## Handoff
- **Current state:** built, PR open, held for the S18 batch.
- **Exact next step:** K-01-T14; T-02 registers the draft-K-1 blocker, T-01-T19 the diagnostics one.
