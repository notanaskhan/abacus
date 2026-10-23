---
id: TASK-959
title: C4 consumer contract tests in backend/tests/contracts/c04_citations_viewer/ (P-03-T03)
spec: SPEC-322
acceptance_criteria: [AC-11, AC-12, AC-13, AC-14]
risk_zone: red
status: done
epic: P-03
plan_key: P-03-T03
branch: s5-trust-kit
created: 2026-10-23
updated: 2026-10-23
---

## Objective
Pin the C4 stub's shapes, refusal codes, human-only actions, flag gates and classification tags, so the implementation (P-03-T05 onward) can't drift from the contract.

## Plan (red zone, tests only)
- **Files:** `backend/tests/contracts/c04_citations_viewer/test_c4_contract.py` (new).
- **Covers:** 404 flag-off and 501 flag-on per route; every route declares exactly one matrix action; agent contexts refused on create, relink, reveal and unlock; OpenAPI shapes and enum codes; every field classified; the unlock password is write-only.
- **Rollback:** revert the commit.

## Progress log
- 2026-10-23: 32 tests, passing against the stub.
