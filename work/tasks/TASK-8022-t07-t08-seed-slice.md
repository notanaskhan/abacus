---
id: TASK-8022
title: "T-07-T08: Brightwater Hale fiduciary and estate slice"
spec: SPEC-656
acceptance_criteria: [AC-15]
risk_zone: amber
status: in-review
branch: t07-t08-seed-slice
worktree: /Users/ayushkbhatia/Accrued/abacus-s44
created: 2026-11-14
updated: 2026-11-14
plan_key: T-07-T08
---

## Objective
Brightwater Hale fiduciary and estate slice.

## Plan
Files: `tax/fiduciary_seed.py` (Calloway and Thornbury constants and loader steps), footing tests `tests/unit/tax/test_t07t08_seed_footing.py`; TS seed `apps/web/src/fixtures/seed/fiduciary.ts` and per-screen scenario key lists. Writes through repositories until the T12/T16/T22 services exist (recorded partial).

## Progress log
- `2026-11-14` — Part 1 built: `fiduciary_slice.py` (figures), `tests/unit/synthetic/test_t07t08_fiduciary_slice.py` (every TXT figure foots), `apps/web/src/fixtures/seed/fiduciary.ts`, `fixtures/scenarios/TXT.ts` (31 keys), `fiduciary.foot.test.ts`. ruff, pyright, eslint, tsc clean; tests at the end pass.
- **Partial (part 2).** Loading through service APIs (T12/T16/T22/T23 services), the opt-in slice and its loader events, the agreement's text layer and scanned page 4, `make fixtures` and the fixture = seed-demo check.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
