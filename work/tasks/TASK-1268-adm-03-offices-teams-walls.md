---
id: TASK-1268
title: ADM-03 Offices, teams, walls & offshore on the T12 frame — offices expand, teams and groups, service lines with the confirm row h, walls with the step-up row, new-wall sheet b, conflict c, offshore d, partner state e, tint f, wall log g (G-01-T14)
spec: SPEC-002
acceptance_criteria: [AC-12, AC-13, AC-17, AC-21, AC-22]
risk_zone: green
status: in-review
epic: G-01
plan_key: G-01-T14
branch: s9a-identity-access
created: 2026-10-26
updated: 2026-10-26
---

## Objective
"Scenarios a–h pass with axe and AY signs off fidelity, with the documented copy deviations."
Screen contract `docs/screens/ADM-03.md`; handoff `ADM-03 Offices- teams- walls and offshore/`
(revision R2 wins over spec).

## Plan
- `apps/web/src/screens/ADM-03/` (index, walls, model, copy, scenarios, test) on `SettingsLayout`
  with the C-13 Fieldset/ValueRow grammar; data only through the generated client; tokens only;
  copy verbatim with the contract's deviations (DEC-43, DEC-73, DEC-352) and DEC-382's.
- Fixtures: `adm03Handlers` and the ADM-03 data in `fixtures/seed/firm-people.ts` (office leads,
  reviewer pools, service-line policies, offshore group, wall actions and log);
  `fixtures/scenarios/ADM-03.ts` a–h; the gallery registration.
- Route `/settings/offices` behind `firm_settings.v2`; the manifest keeps `planned` with its path.
- Tests: one per artboard plus the writes and edges (vitest). Playwright and axe run in G-01-T16
  (Playwright 1.63 wants chromium 1243, only 1248 is cached; not downloaded here).

## Progress log
- 2026-10-26: built; `ADM-03.test.tsx` 14 pass; ADM-01, ADM-02, fixtures, routes and gallery suites
  pass (35 files, 414 tests); `tsc`, eslint and prettier clean on the touched files. Axe not run
  (no jsdom axe harness in the repo's unit tests; G-01-T16's Playwright specs carry it). Fidelity
  sign-off is AY's.
