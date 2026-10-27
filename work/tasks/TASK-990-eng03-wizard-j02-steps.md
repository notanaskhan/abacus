---
id: TASK-990
title: ENG-03 new engagement wizard core on O6 (a, b, c, d, f) and the J02 P-07 journey steps (P-07-T21, P-07-T22)
spec: SPEC-321
acceptance_criteria: [AC-8]
risk_zone: green
status: done
epic: P-07
plan_key: P-07-T21; P-07-T22
branch: s6-eng03-journey
created: 2026-10-23
updated: 2026-10-27
---

## Objective
P-07-T21 and P-07-T22 in one change. ENG-03 at `/engagements/new` behind `engagements.v2` on the
O6 `Wizard` with F-05-T38's TPL-18 type catalogue and gate cards (merged on main before this
task started), over the engagement-types catalogue and one draft; and the J02 journey's P-07 steps.

Acceptance (P-07-T21): "Scenarios a to d and f pass, Next stays disabled with the reason
announced while G1 is unmet, and the f tooltip text is verbatim." Acceptance (P-07-T22): "The
J02-audit-core skeleton walks on staging by Fri Jan 22, 2027 with INV-1, INV-3 and INV-5 asserted
and no serious axe finding."

## What changed
- **ENG-03** `apps/web/src/screens/ENG-03/` and `domain/engagements/wizard.ts`: the six steps
  from the draft's `step`, the gate block (G1 met card with the decider and date, or the G1 needs
  card with "Acceptance is not approved yet (G1)." in a status region and "Start acceptance";
  G2; G3), step 1's Client card (client and entity from `GET /v1/clients/{id}`, the acceptance
  line from G1) and the catalogue (`GET /v1/engagement-types` in three families, plus the static
  Single audit tile with the verbatim tooltip; SOC cards need `attest`), step 2's standards and
  the §103(a)(3)(C) scope, step 4's team with independence chips from G2's blockers and the EQR
  row, autosave on every move with `seen_version` ("Draft · saved 9:39 AM"), "Discard this
  draft?" (DELETE), and Create with an Idempotency-Key opening the new record. Route
  `/engagements/new` (`?draft=`, `?client=`); manifest path set, status kept `planned` (DEC-195).
- **Fixtures** `fixtures/scenarios/ENG-03.ts`: the 18-type catalogue (no `single_audit`), the
  Fairhaven and Granite Peak drafts, the draft routes, and `freshScenario` for tests that write.
- **Journey** `apps/web/e2e/journeys/J02-client-onboarding.spec.ts`, the J02-audit-core skeleton
  F-04-T26 landed while this task ran: its P-07 steps are filled in against the built screens
  (new 3b CLI-02 record from the index; 4 the wizard to Create; 5 the recorded letter and G1 to G3
  met), still `test.fixme` with owners naming what each waits on (DEC-197). Steps 1 and 1 (wall)
  pass in the fixture project.
- **e2e** `e2e/screens/ENG-03.spec.ts`: every scenario with axe; d asserts Next disabled, f the
  tooltip.
- **Contracts** `docs/screens/ENG-03.md`; decision DEC-197.

## Not built, and why
- ENG-03 e, g, h: P-07-T34. Steps 3, 5 and 6 show the draft's facts only (period, portal contact
  count, the engagement name); their editors arrive with P-07-T16's step schemas.
- J02 steps walk only once the fixture app turns `clients.v2` and `engagements.v2` on and the
  live routes land (P-07-T15, T16); the staging walk is the M5 acceptance (Jan 22, 2027).

## Progress log
- 2026-10-23: built and tested; vitest, typecheck, lint, Playwright with axe for every scenario,
  the journey listed in the fixture project, `make check-fast`.
- 2026-10-27 (S10 gap build, P-07-T22): the J02 record steps walk in the fixture project.
  - The fixture app gains `?flags=` (`install.ts`), which turns a flag on in `/v1/me/capabilities`; the seed answers capabilities only when it is given. The harness gains `journey.as(..., { flags })`, used in the fixture project only.
  - The seed scenario now mounts the CLI-02 and ENG-02 record handlers.
  - J02 3b (CLI-02 from its row) and J02 5 (ENG-02b, G1–G3 met, opened from ENG-01) are live in fixture and fixme elsewhere. J02 4 stays fixme because the draft routes answer only in ENG-03's own scenarios.
  - New `e2e/journeys/eng-cli-core.spec.ts`: CLI-01 → CLI-02 and ENG-01 → ENG-02b, with axe and INV-1 to INV-5.
  - Results: fixture project 6 passed, 5 fixme; `src/fixtures` and `src/app-core` vitest 510 passed.
  - Not done: the staging walk (needs the live swaps P-07-T15/T16 and staging).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-197 | ENG-03 core: the draft as the wizard's state, the G1 reason as a status region, the J02 steps as fixme | no |
