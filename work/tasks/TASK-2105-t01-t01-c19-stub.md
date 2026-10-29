---
id: TASK-2105
title: T-01-T01 C19 v1 contract stub (consents, gate and tax-profile family)
spec: SPEC-501
acceptance_criteria: [AC-1, AC-2, AC-3, AC-4]
risk_zone: red
status: in-review
epic: T-01
plan_key: T-01-T01
branch: s16-t01-t01
created: 2026-10-29
updated: 2026-10-29
---

## Objective
C19 v1 as a stub: classified models, 20 routes at 501 behind two flags, the module-API signatures,
matrix rows with agent and system deny, and the contract doc (T-01 §4.3).

## Plan (red)
- `organisations/consents_contract.py`; router and API exports in `organisations/api.py`.
- `permission-matrix/organisations.yaml` (12 actions), `feature-flags/organisations.yaml` (2 flags),
  `fresh-mfa-actions.yaml` (+ group `consent`); `make regenerate`; `make generate`.
- `tests/unit/api/test_app_gates.py` lists (201, 202, 200).
- `docs/contracts/c19-consent-gate.md`, README row; SPEC-501 (T-01's S16 rows).
- Rollback: revert; no table or data.

## Acceptance
`backend/tests/contracts/c19/test_c19_stub.py` (`test_ac1_*` to `test_ac4_*`).

## Progress log
- 2026-10-29: built (S16 block; tests run at the batch's end review). DEC-1155.
