---
id: TASK-8346
title: "T-07-T23: TXT-03 live: the beneficiaries read model, the 8879-F drift void and the release gate's unmet steps"
spec: SPEC-656
acceptance_criteria: [AC-9, AC-10, AC-11]
risk_zone: red
status: in-review
branch: t07-t23-t24-txt03-live
worktree: /Users/ayushkbhatia/Accrued/abacus-s47g04
created: 2026-11-16
updated: 2026-11-16
plan_key: T-07-T23
---

## Objective
Spec section: SPEC-656 F9 to F11; T-07-T23 and T-07-T24 rests. TXT-03 live: the beneficiaries read model, the 8879-F drift void and the release gate's unmet steps.

## Plan (red)
1. `fiduciary_beneficiaries.beneficiaries`: rows only under a current L2 sign-off on the computation (else TXT-03 e); each beneficiary's code allocation (`beneficiary_allocations`), payments, K-1 package and delivery (a firm client hand-off or the portal); totals with line 18's IDD and the tie; the 65-day card (window, distributions in it, the latest election, its owner); the release steps from `k1_release.eligibility`.
2. T-07-T24 (DEC-85): a person's recompute that creates a new version supersedes every live Form 8879-F envelope on the return (`signatures.api.supersede_for_amount_change`, bound to the new computation), so the gate reads unmet until the trustee signs again.
3. The release refusal names `gate_unmet` (the unmet 1041 steps in order) beside `failing`.

## Progress log
- `2026-11-16` — Built in the S47 sequential stack (DEC-5331). Lint, pyright and the banned patterns clean; the app imports; client regenerated. Partial: the trustee question draft (no request-template read in requests' API yet), creating draft 1041 K-1 packages outside the CCH import, the 65-day paragraph template (DV-5), the system recompute's drift void, the release steps' who and when, and the TY2027 8879-F form-set row (refdata CLI, human). Gates and
  tests run once at the S47 end pass (build first, test last).
