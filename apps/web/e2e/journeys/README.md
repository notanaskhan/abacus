Journey specs (J01-J28) land here, one file per journey (`.claude/skills/journey-e2e`).
They import the harness (`../harness`, F-04-T21): `test` with a `journey` fixture whose
`journey.as(persona, path)` signs a persona in through the project's adapter and whose
`journey.step(name, run)` runs axe (serious and critical = 0) and INV-1 to INV-5 after the step.

Each spec runs in four Playwright projects: `fixture` (`make journeys`, no Docker), `fullstack`
(`make journeys-full`, against `make dev` + `make seed-demo`), and `staging` and `canary` (their
URL in `ABACUS_STAGING_URL` / `ABACUS_CANARY_URL`; they skip while it is unset).

- `J02-client-onboarding.spec.ts`: J02-audit-core (F-04-T26).
- `eng-cli-core.spec.ts`: the P-07 screens in the app on fixtures, CLI-01 → CLI-02 and ENG-01 → ENG-02b (P-07-T22).
- `J03-ebp-audit.spec.ts`, `J06-individual-1040.spec.ts`, `J10-month-end-close.spec.ts`, `J16-daily-practice.spec.ts`, `J22-unrecorded-liabilities.spec.ts`: the P-06 steps (P-06-T25).
- `J12-client-portal.spec.ts`: J12-core (F-04-T26).
- `J04-fs-audit.spec.ts`: J04-fs-audit's PBC slice at the Sep 24 snapshot (F-04-T32; M6).
- `J01-firm-onboarding.spec.ts`: J01-core skeleton (F-04-T32; M8).

In the fixture project, `journey.as(persona, path, { flags, scenario })` can do two things before a screen's live swap:
- `flags` turns on flags E0 leaves off (`?flags=`).
- `scenario` lays a screen's own fixture scenario over the seed (`?scenario=BND-02:b`).

A `_key_` segment or query value in the path (`/binders/_binderId_?ov=request:new:_binderId_`) is replaced by the id the scenario's `OPENS` names.

A step whose screen is still planned is `test.fixme` with an `owner` annotation: the epic, the task
and its sprint end date. CI (F-04-T28): pull requests run the `fixture` project when the SPA, the
portal, the UI library or the journeys change; the nightly runs `fullstack` on the runner's own
stack; the staging job is off until staging exists (`STAGING_JOURNEYS`).
