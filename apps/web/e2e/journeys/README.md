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
- `J04-fs-audit.spec.ts`: J04-fs-audit's PBC slice at the Sep 24 snapshot (F-04-T32; M6), and the trace to source, AUD-03's screening citation → SHL-07 → SHL-08 with the region lit (P-03-T25; full stack and staging).
- `../trust/pii-reveal-unlock.fullstack.spec.ts`: the masked W-2, the logged reveal and its refusals, and the password PDF unlocked to masked pages (P-03-T25; full stack and staging). Files named `*.fullstack.spec.ts` anywhere under `e2e/` run on the harness projects.
- `J01-firm-onboarding.spec.ts`: J01-core skeleton (F-04-T32; M8); step 3 and 3f live in fixture mode (G-01-T16).
- `J14-firm-admin.spec.ts`: j14 1, 2 and 2b, Lena Park's seasonal seat and wall (G-01-T16).
- `J16-daily-practice.spec.ts`: j16 2, Firm settings from the firm pill (G-01-T16).
- `cli-06-intake.spec.ts`: CLI-06 i (validation jumps back), h (a manager clears a hit, INV-1) and g (the CCH client-list import: 204 + 8 + 0, "Import 210 records", the counts) (P-07-T62).
- `J19-estate-amended.spec.ts`: j19 0 (Grace adds the estate under Walter Thornbury, conflict check and screening, Create & start acceptance), j19 2 (Daniel accepts with conditions) and j19 3 (the estate engagement's three returns); steps 1 and 4–8 fixme with owners (P-07-T62).
- `eng-13-roll-forward.spec.ts`: ENG-13 d (Northwind PY2025 → PY2026, 24 requests as Draft) and e (Tessellate, fixture until X-01) through the route (P-07-T62).
- `portal-keyboard.spec.ts`: the portal's keyboard-only drop (POR-03) and sheet (POR-04) paths (R-01-T31).
- `A02-tb-connections.spec.ts`: j04 2 (Granite Peak's TB on AUD-06), j02 6 (Tess connects QuickBooks Online and the bank feed on POR-16 e → b → c → a), j03 7 (Northwind's TB with its ties) and POR-16's reconnect, on the screens' artboards in the fixture project; the live runs are `test.fixme` until A-02's live swaps reach staging (A-02-T34).
- `R01-templates.spec.ts`: j16 4 (Grace edits, tests and publishes Reminder v4 on POR-20 a → j → k → l) in the fixture project; j12 1 (the sink), j02's database invitation and the M8 j12-core canary walk are `test.fixme` until R-01's live swap reaches staging (R-01-T32).
- `../signatures/{sig-01-hub,sig-02-builder,por-06-sign,eng-04-letter}.fullstack.spec.ts` and the `J02`, `J15` and `J16` signature blocks (j02 4 and 4c, j15 4, j16 7): N-02's screens on the harness; ENG-04 on its real route and POR-06 through `/sign` on their own scenarios, SIG-01 and SIG-02 on their artboards (no route of their own yet); the hosted walks are N-02-T42's M13 journeys (N-02-T40).
- `gates-access.spec.ts`: P-07's gates and access, CLI-04's invite, CLI-07 and CLI-08 as human-only gates, and J03 steps 1 and 2, on the screens' own scenarios (P-07-T53; DEC-645).

A step on a screen behind a flag E0 leaves off may open the real route on the screen's own fixture scenario with `?screen=<ID>&st=<state>` (fixture project only; DEC-457).

In the fixture project, `journey.as(persona, path, { flags, scenario })` adds two switches:

- `flags` turns on flags E0 leaves off (`?flags=`).
- `scenario` is the `?screen=` choice above, written `BND-02:b`.

A `_key_` segment or query value in the path (`/binders/_binderId_?ov=request:new:_binderId_`) resolves to the id the state opens (`ids` in `screen-scenarios.ts`).

A step whose screen is still planned is `test.fixme` with an `owner` annotation: the epic, the task
and its sprint end date. CI (F-04-T28): pull requests run the `fixture` project when the SPA, the
portal, the UI library or the journeys change; the nightly runs `fullstack` on the runner's own
stack; the staging job is off until staging exists (`STAGING_JOURNEYS`).
