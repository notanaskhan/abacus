---
id: TASK-7619
title: P-02-T11 SHL-02 fixtures and scenarios a–g, loading and error
plan_key: P-02-T11
spec: SPEC-000  # docs/screens/SHL-02.md; C15 v1
acceptance_criteria: [AC-1]  # every artboard a scenario with a test; e renders no wall count; parity reported
risk_zone: green
status: in-review
branch: p02-t11-fixtures
worktree: /Users/ayushkbhatia/Accrued/abacus-s40
created: 2026-11-12
updated: 2026-11-12
---

## Objective
SHL-02's fixtures on the Brightwater Hale seed: one response per artboard (a–g), loading and error,
the fixture handlers for the three C15 routes, and footing tests.

## Plan
- `apps/web/src/fixtures/seed/shl02.ts` (new): a ("feld"), b (recents), c (agent mode), d (the
  suggestion), e (a without two walled Feld documents), f ("granite", Sep 28), g ("explain").
- `apps/web/src/fixtures/handlers/search.ts` (new), `apps/web/src/fixtures/scenarios/SHL-02.ts`
  (new; `QUERIES` per state).
- Footing test `apps/web/src/fixtures/shl02.foot.test.ts`.
- The per-artboard screen tests and the screen-scenario registration land with the palette
  frontend (P-02-T10), which renders them.
- Rollback: delete the files.

## Partial
- Parity (Tier C report, Tier D computed styles) runs at the visual project, not in this session.

## Progress log
- `2026-11-12` — Fixtures, handlers and scenarios built. Tests at the S40 end pass.
