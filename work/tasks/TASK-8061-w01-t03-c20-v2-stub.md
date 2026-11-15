---
id: TASK-8061
title: "W-01-T03: C20 v2 Connect contract stub, seed-derived fixtures, contract doc v2 section"
spec: SPEC-659
acceptance_criteria: [AC-1, AC-2, AC-3, AC-6, AC-20, AC-23]
risk_zone: red
status: in-review
branch: w01-t03-c20-v2-stub
worktree: /Users/ayushkbhatia/Accrued/abacus-s45
created: 2026-11-15
updated: 2026-11-15
plan_key: W-01-T03
---

## Objective
Contract first for Connect: classified models, 501 routes under their actions behind
`integrations.connect_v1`, the catalogue as scenario data, FE fixtures for every WB-10 and WB-11
artboard.

## Plan (red module)
1. `integrations/connect_contract.py`; router in `integrations/api.py`; error catalogue; `make generate`.
2. Scenario content `files/connect_catalog.json` + `connect_catalog.py`; FE copy, `seed/connect.ts`,
   `scenarios/connect.ts`.
3. `docs/contracts/c20-integrations.md` v2 section.
4. `fixtures/contracts/connect-figures.test.ts` (Python consumer tests ride W-01-T06).

## Progress log
- `2026-11-15` — Planned at the S45 kickoff (TASK-8029).
- `2026-11-15` — Built (DEC-5046). ruff, pyright, tsc and eslint clean; footings checked by a
  one-off run. **Mistake a third time:** a generic schema name (`ConsentOut`) collided in the
  OpenAPI document; the lint candidate (unique schema names and operation ids) is now overdue.
