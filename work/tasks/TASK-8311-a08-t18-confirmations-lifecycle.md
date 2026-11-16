---
id: TASK-8311
title: "A-08-T18: Confirmations lifecycle"
spec: SPEC-657
acceptance_criteria: [AC-6]
risk_zone: amber
status: in-review
branch: a08-t18-confirmations-lifecycle
worktree: /Users/ayushkbhatia/Accrued/abacus-s47g04
created: 2026-11-16
updated: 2026-11-16
plan_key: A-08-T18
---

## Objective
Spec section: docs/specs/SPEC-657-a08-audit-fieldwork-depth.md F5.
Confirmations lifecycle.

## Plan (amber)
1. `assurance/confirmations_lifecycle.py`: send (address gate, a link principal for `accrued_link`, recorded otherwise), second request (once), the follow-up rule (`follow_up_step`, `follow_up`), recorded responses, reconciliation with code-computed unreconciled against the engagement's clearly trivial, manager acceptance never by the reconciler (content hash), alternative procedures, close (C3, C4).
2. `assurance/confirmations_contract.py`: the T18 routes call the service.
3. Audit kinds reviewed. Tests: `tests/unit/assurance/test_a08t18_confirmation_lifecycle.py`.

## Progress log
- `2026-11-16` — Built in the S47 sequential stack (DEC-5308). Lint and pyright clean; the app imports; the unit file ran green (3 tests). Partial: the C7 authorization envelope and its completion subscriber, the templated send emails, the exception prefill route and Below-CT misstatement routing, and `ConfirmationFollowUpWorkflow` itself (its tick is `follow_up`) are not built; revoke-link still answers 501. Gates and
  tests run once at the S47 end pass (build first, test last).
