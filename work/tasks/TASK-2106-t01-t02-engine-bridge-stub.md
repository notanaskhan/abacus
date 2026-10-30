---
id: TASK-2106
title: T-01-T02 Tax-engine bridge and e-file record contract stub
spec: SPEC-501
acceptance_criteria: [AC-5, AC-6, AC-7, AC-8]
risk_zone: red
status: in-review
epic: T-01
plan_key: T-01-T02
branch: s16-t01-t02
created: 2026-10-29
updated: 2026-10-29
---

## Objective
The TAX-09, TAX-12 and ADM-08 family as stubs: models, 27 routes at 501 behind two flags, matrix
rows with agent and system deny, the contract docs and the tax seam note (T-01 §4.3).

## Plan (red)
- `tax/engine_contract.py`, `integrations/engine_settings_contract.py`; routers and `tax.api`.
- `permission-matrix/{tax (new), integrations, identity}.yaml`; `feature-flags/tax.yaml` (new);
  fresh-MFA rows; `make regenerate`, `make generate`; `test_app_gates` lists.
- `docs/contracts/tax-engine-bridge.md`, `efile-record.md`; tax README seam note.
- Rollback: revert; no table or data.

## Acceptance
`backend/tests/contracts/tax_engine/test_engine_stub.py` (`test_ac5_*` to `test_ac8_*`).

## Progress log
- 2026-10-29: built (S16 block; tests run at the batch's end review). DEC-1156.
