---
id: TASK-2101
title: K-02-T02 C21 v1 contract stub
spec: SPEC-500
acceptance_criteria: [AC-4, AC-5, AC-6, AC-7]
risk_zone: amber
status: in-review
epic: K-02
plan_key: K-02-T02
branch: s16-k02-t02
created: 2026-10-29
updated: 2026-10-29
---

## Objective
C21 v1 as a stub: the models for seven reference-set kinds and eight standard kinds, every
K-02 route at 501 behind its flag, the frozen module-API signatures, the generated client, the
contract doc and the KNW-04 screen contract (K-02 §4.3–§4.5, §8).

Acceptance (backlog row): "The stub merges by Thu Jun 3, 2027 and the T-01 and T-02 consumer
contract tests run green against it in K-02's CI."

## Plan (amber)
- `platform/reference_sets_contract.py`, `practice/due_dates_contract.py`,
  `methodology/standards_contract.py`; routers in each module's `ROUTERS`; module APIs re-exported.
- Status registry: `firm_standard_version`, `reference_set_version` (`make regenerate`; status pins
  102 objects / 479 rows in `apps/web/src/status/status.test.ts`).
- `make generate`; regenerated route-introspection and fresh-MFA suites; `test_app_gates` lists
  (201 for create, draft and imports; 200 for publish).
- Docs: `docs/contracts/rules-tables.md`, `docs/screens/KNW-04.md`, contracts README row.
- No migration, no audit action. Rollback: revert; routes and module APIs disappear.

## Acceptance
| Check | Test |
|---|---|
| Routes declare actions and are stubs; no reference-set writes | `test_ac5_*` in `backend/tests/contracts/c21_rules_tables/test_c21_stubs.py` |
| Fields classified; kinds; discriminators; families; auto-accept off | `test_ac4_*` |
| Client 404; flags 404/501 | `test_inv4_*`, `test_ac5_flag_off_is_404_and_on_is_501`, `test_ac5_the_standards_flag_*` |
| Module APIs exported, raising, naming their version | `test_ac6_*` |
| T-01/T-02 consumer tests | T-01-T04 (`c21_t01`), T-02-T05 (`c21_t02`) |

## Progress log
- 2026-10-29: built (S16 block; tests written first, run at the batch's end review). DEC-1151.
