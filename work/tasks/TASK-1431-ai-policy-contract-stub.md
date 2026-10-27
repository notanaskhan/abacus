---
id: TASK-1431
title: AI-policy contract stub, ADM-04 family (G-02-T15)
spec: SPEC-349
acceptance_criteria: [AC-31, AC-32, AC-33, AC-34, AC-35, AC-36, AC-37, AC-38, AC-39, AC-40, AC-41, AC-42, AC-43, AC-44]
risk_zone: red
status: in-review
epic: G-02
plan_key: G-02-T15
branch: s11-security
created: 2026-10-27
updated: 2026-10-27
---

## Objective
Contract first for ADM-04 (ADR-186, ADR-187): classified models for policy versions, sections A
to E, gate rows, immediate controls, sub-processors, diffs and publish requests; eleven routes
answering 501 behind `ai_policy.v1`, each under one matrix action; fixtures serving ADM-04 a, b,
d, e, g, h, i, j, the band and Awaiting approval; `docs/contracts/ai-policy.md` with the
effective-policy read for P-10, K-02, P-07 and N-02.

## Plan
- `backend/src/abacus/modules/agents/ai_policy_contract.py` (models and the stub router, mounted
  in `agents.api.ROUTERS`); the matrix rows exist (G-02-T02). No migration, no flag edit.
- `docs/contracts/ai-policy.md` and its register row; `make generate`.
- Tests: `tests/contracts/ai_policy/test_ai_policy_contract.py`; `test_app_gates` classifies the
  three 200 POST routes.
- Fixtures: `apps/web/src/fixtures/{seed/ai-policy.ts, handlers/ai-policy.ts,
  scenarios/ADM-04.ts, contracts/ai-policy.contract.test.ts}`.
- Rollback: revert; the routes disappear (nothing reads them yet).

## Progress log
- 2026-10-27: built. DEC-532 (shapes; gate rows from chapter 05 §5.2.13 as codes; v2/v3 diff
  lines, the model family and the opt-in's register version left empty rather than invented
  because the handoff is not in the repository and the provider-terms register is empty).
  c and f (dormant principal) and k stay with T25 and I-03-T37.
- 2026-10-27: contract test and fixture contract test green; `_stub` read through a helper
  (TYPE-001). Gates green.
