---
id: TASK-8047
title: "A-08-T05: fieldwork-testing, audit-analytics and SSARS contract stubs, consumer tests"
spec: SPEC-657
acceptance_criteria: [AC-0.4, AC-0.5]
risk_zone: amber
status: in-review
branch: a08-t05-fieldwork-stubs
worktree: /Users/ayushkbhatia/Accrued/abacus-s45
created: 2026-11-15
updated: 2026-11-15
plan_key: A-08-T05
---

## Objective
Contract first for AUD-12, AUD-13 and AUD-26: Pydantic models with classifications, 501 routes
under one action each behind their flags, seed-derived typed fixtures, contract docs, and the
consumer tests over these stubs and the confirmations stub (merged from T07).

## Plan (amber: written before the build)
1. `sampling/fieldwork_contract.py`, `workpapers/fieldwork_tests_contract.py`,
   `assurance/analytics_contract.py`; routers registered; error catalogue; `make generate`.
2. `assurance/fieldwork_fixtures.py` (computed footings); `apps/web/src/fixtures/seed/fieldwork.ts`.
3. `docs/contracts/{fieldwork-testing,audit-analytics,ssars-workspace}.md`.
4. Tests: `tests/contracts/a08_fieldwork/test_fieldwork_stubs.py`,
   `apps/web/src/fixtures/contracts/fieldwork-figures.test.ts`.
Rollback: revert; no table, no write.

## Progress log
- `2026-11-15` — Planned at the S45 kickoff (TASK-8029); plan above written before building.
- `2026-11-15` — Built (DEC-5032). ruff, pyright, tsc and eslint clean on touched files; the
  footings checked by a one-off import (236; 14 = 8 + 6; 4,174,000; 15.3%). Tests run at the end pass.
- **Mistake caught:** a second `CoverageOut` model renamed AUD-08's type in the generated client;
  renamed ours `ConfirmationCoverageOut`. Candidate lint: unique Pydantic model names across modules.
