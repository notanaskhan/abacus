---
id: TASK-2213
title: T-01-T12 TRI MFA predicate, offshore provider and SSN unlock
spec: SPEC-501
acceptance_criteria: [AC-24, AC-25, AC-26, AC-27]
risk_zone: red
status: in-review
epic: T-01
plan_key: T-01-T12
branch: s17-t01-t12
created: 2026-10-30
updated: 2026-10-30
---

## Objective
Register the TRI predicate in P-08's `register_mfa_requirement` slot for grants scoped to
`tax_return` work items and K-1 packages; register the `offshore_disclosure` provider in G-01's
slot; lift P-07's SSN and ITIN refusal on real tenants once the C19 provider is registered; TRI
tags on TIN columns and serializer masking for offshore members (T-01 §3.3, §3.4).

Acceptance (backlog row): "Claire Feld must complete two-step verification on her 1040 scope,
an offshore member sees only consented clients with masked TINs, and SSN entry works on a real
tenant only after the gate is registered."

## Plan (red)
- `engagements/work_items.py`: `mfa_tri_scope`; `engagements/api.py` registers `tri_scope`.
- `identity/mfa_floor.py` (protected): `FLOOR` adds `tri_scope`; identity exports
  `active_grants`, `GrantRow`, `OFFSHORE_DISCLOSURE`.
- `organisations/consent_gate.py`: the offshore check, predicate (`offshore_column`) and count,
  registered with the TRI checks.
- `organisations/tin.py`: the seal path's SSN and ITIN refusal lifts when the three C19 checks
  are registered.
- `organisations/contract.py`: `tri=True` on `MaskedTinOut.last4` and `TinRevealOut.value`
  (generated client regenerates).
- Tests: `tests/integration/test_t01t12_tri_rails.py`; the seal-path refusal tests
  (`test_tin_reveal.py`, P-07-T13's suite) pin the before-gate state and gain an after-gate
  case; `test_mfa_floor.py` names the third predicate.
- No migration, no matrix change, no flag. Rollback: revert (the refusal returns).

## Acceptance
| Check | Test |
|---|---|
| Claire's 1040 scope needs MFA; engagement and K-1 scopes; others not | `test_ac24_*` |
| Offshore provider: every entity, in force, predicate and count agree | `test_ac25_*` |
| Offshore assignment needs consent; TINs masked | `test_ac26_*`, `test_ac27_*` |
| SSN on a real tenant before and after the gate | `test_tin_reveal.py`, `test_p07t13_*` (pinned), `test_t01t12_an_ssn_on_a_real_firm_*` |

## Progress log
- 2026-10-30: built in S17 Lane 2 on T-01-T11; tests run in the end review.
