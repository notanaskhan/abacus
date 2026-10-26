---
id: TASK-1360
title: Playwright journey steps j01 3, j14 1-2, j16 2 and the ADM-01/02/03 screen specs (G-01-T16)
spec: docs/plan/epics/G-01.md section 10
acceptance_criteria: ["The named scenarios pass nightly in compose and on staging after the batch deploy."]
risk_zone: green
status: in-review
epic: G-01
plan_key: G-01-T16
branch: s10c-ops
created: 2026-10-27
updated: 2026-10-27
---

## Objective
Write the G-01 journey steps and screen specs so they run in fixture mode now and switch on for the
full stack and staging when E0 turns `firm_settings.v2` on.

## Plan
- `apps/web/e2e/journeys/J01-firm-onboarding.spec.ts`: j01 3 (offices, ADM-03a), j01 3 seats full
  (ADM-02c), j01 3f (Lena Park's pending invite on Jan 5, ADM-02f): live in `fixture`.
- `J14-firm-admin.spec.ts` (new): j14 1 (Lena Park, Denver, seasonal end, offshore group empty),
  j14 2 (the new wall, Neil Ashcroft refused, the log naming Grace and Margaret), j14 2b (as Lena,
  CLI-01 without Ashford, INV-3 out-of-scope).
- `J16-daily-practice.spec.ts` (new): j16 2, Firm settings from the firm pill with ADM-01 live.
- `e2e/screens/ADM-01.spec.ts`, `ADM-02.spec.ts`, `ADM-03.spec.ts`: every state from the gallery,
  axe on the frame and the overlay.
- Fixture mode (DEC-457): `src/fixtures/screen-scenarios.ts` lets the firm entry serve a built
  screen's own scenario (`?screen=ADM-03&st=b`, applying the state's OPENS when the URL has no
  search of its own), as the portal entry's `?st=` does; `install.ts` uses it. Vitest
  `screen-scenarios.test.ts`.
- Full stack, staging and canary: `test.fixme` with owner annotations until E0 turns
  `firm_settings.v2` on and the nightly seeds the people slice (G-01-T17), and the batch deploy
  carries it (G-01-T19).

## Not done
- The nightly compose run: E0 (`make seed-demo` in `e2e.yml`) does not turn `firm_settings.v2` on
  nor load the `people` slice, so the steps are fixme on `fullstack`; changing the nightly seed
  is a CI workflow change left to G-01-T17.
- Playwright was not run: the local chromium does not match the pinned Playwright (known), so
  the specs are type-checked, linted and formatted only.

## Progress log
- 2026-10-27: written (DEC-457).
