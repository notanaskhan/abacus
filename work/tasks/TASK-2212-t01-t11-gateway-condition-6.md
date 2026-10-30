---
id: TASK-2212
title: T-01-T11 gateway condition 6 and the TRI gate
spec: SPEC-501
acceptance_criteria: [AC-17, AC-18, AC-19, AC-20, AC-21, AC-22, AC-23]
risk_zone: red
status: in-review
epic: T-01
plan_key: T-01-T11
branch: s17-t01-t11
created: 2026-10-30
updated: 2026-10-30
---

## Objective
Gateway condition 6 and the TRI gate (T-01 §3.2; ADR-167; ADR P-12): the `consent(<purpose>)`
matrix condition with generated tests; consent-check providers for `use` and `ai_disclosure` per
taxpayer, tax year and every required signer; boundary reason `consent_7216` on
`AssembledContext.data_subjects` on every route including `fake` and before the synthetic pass;
no cached consent facts; audited refusal and metric; spec validation refusing `data_classes: tri`
without the registration; access events for every TRI agent read; TIN masking in `sanitise.py`.

Acceptance (backlog row): "A synthetic Ferris context is refused with consent_7216 and audited,
a revocation takes effect on the next call, and existing audit-agent boundary tests stay green."

## Plan (red)
- `ai_gateway/context.py`: `DataSubject`, `AssembledContext.data_subjects`,
  `ContextBuilder.subjects()`.
- `ai_gateway/boundary.py`: reason `consent_7216` (appended, index 9),
  `register_tri_consent_check`, `tri_consent_registered`, `enforce_tri_consent`;
  `enforce_boundary(..., subjects=)` checks it after `ai_paused`, before everything else.
- `ai_gateway/__init__.py`: the check before budget and admission and before each attempt;
  `tri.agent_read` access events per subject and covering consent.
- `ai_gateway/sanitise.py`: `mask_tins` in `sanitise_text`, counted.
- `organisations/consent_gate.py` (new): the 0402 read (`consent_state`, `tri_consent_verdict`,
  `covering_consents`, `require_tri_consent`, `consent_given` providers for `use` and
  `ai_disclosure`); `engagements/api.py` registers `covering_consents` with the gateway
  (P-07-T04 forbids organisations importing it).
- `identity/authz`: `consent` condition (matrix parser, `Rule.consent`, `ConditionFacts.consents`,
  `TargetFacts.consent_subjects`, fresh resolution through `consent_given`); `slots.consent_registered`.
- `agents/spec.py`: `data_classes`, `validate_data_classes`.
- `abacus_tools/codegen/security_tests.py` and `tests/security/matrix_harness.py`: consent variants.
- No migration, no matrix row change, no flag (a compliance control is never a rollout toggle).
- Tests: `tests/unit/ai_gateway/test_t01t11_consent_7216.py`,
  `tests/unit/identity/test_t01t11_consent_condition.py`,
  `tests/integration/test_t01t11_consent_gate.py`. Existing boundary suites run unchanged.
- Rollback: revert; the boundary loses `consent_7216` and `tax_return_information` still fails
  closed for real firms.

## Acceptance
| Check | Test |
|---|---|
| Ferris refused with consent_7216 and audited, every route, synthetic too | `test_ac17_*` (unit and integration) |
| Both consents: proceeds; access events | `test_ac18_*` |
| Revocation, expiry, year, material terms | `test_ac19_*` |
| Unresolved subject; require_tri_consent | `test_ac20_*` |
| consent(<purpose>) condition and generated cases | `test_ac21_*` |
| tri spec validation | `test_ac22_*` |
| TIN masking | `test_ac23_*` |

## Progress log
- 2026-10-30: built in S17 Lane 2 (AY on N's red row, as in S9); tests run in the end review.
