---
id: TASK-315
title: "F-03-T18 + T19: frozen-contract snapshots in CI; C1 and C2 frozen at v1 with consumer tests; G1–G3 gate facts on the engagement read"
spec: SPEC-306
acceptance_criteria: [AC-1, AC-2, AC-3]
risk_zone: amber
status: done
branch: task-315-contracts
worktree: spec005
created: 2026-10-21
updated: 2026-10-21
---

## Plan
- `abacus_tools/contracts.py`: snapshots of each frozen contract's OpenAPI schemas in `backend/tests/contracts/<contract>/vN.json`.
  - `--check` fails on a removed or renamed field, a changed type, a field made required, or a removed enum member. Additions pass.
  - `--freeze` writes a new version and never rewrites one.
  - `make ci-contracts` runs the check and `tests/contracts`.
- C1 v1 (`work-items.md`):
  - G1–G3 gate providers in `engagements/gates.py`, registered in the fail-closed slot;
  - `EngagementOut.gates` filled on `GET /v1/engagements/{id}`;
  - consumer tests: 14 types with none excluded, the 8 lifecycle codes, service line, the G1–G3 gate shape, the five work-item kinds, the per-type gate policy.
- C2 v1 (`status-registry.md`): consumer tests check that every API status enum is its object's stored codes, that no derived code is stored, and that the UI data is generated.
- Register rows: C1 and C2 frozen, C15 slot reserved. DEC-122 records it and resolves DEC-116.

## Definition of done
- [x] `tests/contracts` (16) passes.
- [x] `tests/unit/engagements/test_gates.py` (3) passes.
- [x] Engagement integration (158) passes.
- [x] `contracts --check` is clean.
- [x] check-fast passes.
