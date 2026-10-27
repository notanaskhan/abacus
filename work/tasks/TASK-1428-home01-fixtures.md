---
id: TASK-1428
title: HOME-01 fixtures and scenarios, seed footing tests (I-01-T05)
spec: SPEC-313
acceptance_criteria: [AC-1]
risk_zone: green
status: in-review
epic: I-01
plan_key: I-01-T05
branch: s11-home
created: 2026-10-27
updated: 2026-10-27
---

## Objective
Every HOME-01 artboard and spec-only state as a fixture scenario typed against the generated
client, with footing tests: 17 + 15 + 11 + 7 = 50 of 79, 27 audits, 11 of 22 closes, 9 notices
with 2 New, 11 = 3 + 6 + 2.

## Plan
- Contract first (DEC-573): `HumanGateOut` gains `band`, `blocked`, `blocked_reason_code`, and the
  `title` and `context` slots the owners' resolvers fill (I-01-T07; null live until then);
  `make generate`.
- `fixtures/seed/home.ts` (handoff rows verbatim), `fixtures/handlers/home.ts`,
  `fixtures/handlers/human-gates.ts` (list and counts from the same rows; walls; office filter),
  `fixtures/scenarios/HOME-01.ts` (a, a2, b-e, f, g, h, i, office-denver, tile-popover,
  today-brief-off, walled), `fixtures/screen-scenarios.ts`.
- `fixtures/home.foot.test.ts`.

## Progress log
- 2026-10-27: built. Client activity rows are I-01-T12's projection (empty in the fixture); h and
  i carry Hannah's and Marcus's own (empty) gate sets, their R2 bands are I-01-T24's.
- 2026-10-27: targeted pass green (backend pytest -n 2 on the new and directly covering files, vitest on the touched FE files); gates clean (ruff, pyright, lint-imports, quality tools, check-heads, check-generated, tsc, eslint, prettier, vite build, bundle budget 245.9 of 250 KB). Playwright and axe-in-browser not run in this lane.
