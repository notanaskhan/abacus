---
id: TASK-3253
title: A-07-T06 consumer contract tests for both A-07 stubs; the refusal codes
spec: SPEC-644
acceptance_criteria: [AC-6]
risk_zone: amber
status: in-review
epic: A-07
plan_key: A-07-T06
branch: s27-a07-t06
worktree: /Users/ayushkbhatia/Accrued/abacus-s27
created: 2026-11-04
updated: 2026-11-04
---

## Objective
"The suite runs in notanaskhan's CI against the stubs and fails if any artboard field lacks a
server source."

## Plan (amber)
- `backend/tests/contracts/audit_completion/test_audit_completion_stubs.py`: 55 operations with
  their action and 404/501; every field classified; clients hold nothing; the agent only reads
  and runs code; 24 artboard field sources; the refusal codes are catalogued.
- `apps/web/src/domain/audits/completion-contract.test.ts`: AUD-18 a, AUD-19 a, AUD-24 a and
  AUD-25 a/c typed by the generated schemas (`satisfies`), pinning 6 of 10, 12 of 17, 8 of 9,
  the gate cards, Dec 8 and the seal prefix.
- `assurance/completion_errors.py`: the A-07 §4.3 refusal classes (`archived`, `gates_not_met`,
  `checklist_incomplete`, `eqr_only`, `eqr_ineligible`, `ep_only`, `approval_required`,
  `decision_required`, `item_derived`, `internal_amount_in_text`, `date_mismatch`,
  `content_changed`, `stale_version`, `seal_mismatch`, `release_mode_external`,
  `paragraph_locked`), so `error-codes.yaml` lists them before the services raise them.
- Rollback: revert; regenerate the catalogue.

## Progress log
- 2026-11-04: built; catalogue regenerated (11 new codes; 403s are not catalogued). Tests at the
  S27 end review.

## Decisions made during this task
DEC-2233.
