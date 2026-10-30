---
id: TASK-2208
title: K-02-T05 reference-set service
spec: SPEC-500
acceptance_criteria: [AC-15, AC-16, AC-17, AC-18, AC-19, AC-20]
risk_zone: amber
status: in-review
epic: K-02
plan_key: K-02-T05
branch: s17-k02-t05
created: 2026-10-30
updated: 2026-10-30
---

## Objective
The C21 part A service in `platform`: the kind registry and validators (seven kinds; a
`standards_sets` draft limited to `gaas_nonissuer`, `ssars` and `sqms` with no PCAOB or issuer
set and no published code dropped or re-familied), effective-dated resolution (latest
`effective_from` on or before `as_of`, ties to the highest version), the `platform.api` readers,
and live `GET /v1/reference-sets` endpoints (K-02 §4.3–§4.5).

Acceptance (backlog row): "A re-published correction wins for its effective date, the prior tax
year's set answers before that date, every response names its version id, and a standards_sets
draft holding a PCAOB or issuer set, or removing an existing code, is refused (X-07)."

## Plan (amber)
- `platform/reference_sets.py` (new): `KINDS`, `validate_payload`, `validate_standards_sets`,
  `check_draft`, the readers over 0400's definer functions inside `platform_transaction`
  (`reference_set_resolve`, `_list`, `_history`; `.columns()` types the jsonb), and the module
  API. Errors `reference_kind_unknown`, `reference_payload_invalid`, `standards_set_refused`
  (422, catalogued).
- `platform/reference_sets_routes.py` (new): the router moves out of the contract module (the
  service imports the contract's models, so the routes cannot live there without a cycle).
  Client 404, then `reference_set.read`, then the flag; unknown key or nothing in effect 404.
- `reference_sets_contract.py` keeps the models and result dataclasses only; `platform.api`
  re-exports the service.
- No migration, no matrix or flag change (the action and flag exist since K-02-T02). The
  generated client regenerates (the routes no longer document 501).
- Tests: `tests/integration/test_k02t05_reference_set_service.py` (Postgres, probe keys),
  `tests/unit/platform/test_reference_set_kinds.py`; `c21_rules_tables/test_c21_stubs.py` and
  `c21_t01/test_c21_t01_consumer.py` move from "stub" to "live" expectations.
- Rollback: revert; the routes return to 501 and the readers to `NotImplementedError`.

## Acceptance
| Check | Test |
|---|---|
| Correction wins; prior set before; nothing in effect | `test_ac15_*` (integration) |
| Drafts never served | `test_ac16_a_draft_is_never_served` |
| Readers name their version | `test_ac17_*` |
| Routes, 404s, client 404 | `test_ac18_*`, `test_inv4_*`; `test_c21_stubs.py` gate tests |
| PCAOB / issuer / dropped / moved codes refused | `test_ac19_*` (unit and integration) |
| Kind registry | `test_ac20_*` |

## Progress log
- 2026-10-30: built in S17 Lane 2; tests written, run in the end review (build first).
