---
id: TASK-997
title: J02-audit-core and J12-core skeleton journey specs; CI wiring for PR fixture journeys and nightly full-stack and staging runs (F-04-T26, F-04-T28)
spec: SPEC-307
acceptance_criteria: [AC-8]
risk_zone: red
status: done
epic: F-04
plan_key: F-04-T26; F-04-T28
branch: s6-f04-journeys-ci
created: 2026-10-23
updated: 2026-10-23
---

## Objective
- T26: "Both specs run on staging by Jan 22 with INV-1 to INV-5 and axe, and unbuilt steps are test.fixme with an owning epic."
- T28: "PR and nightly jobs publish traces and axe reports and never point a local build or seed at a hosted database."

## Plan (red: written before the code)
- **Specs (T26):**
  - `apps/web/e2e/journeys/J02-client-onboarding.spec.ts` ("J02-audit-core"; F-04.33 calls it `j02-client-onboarding`);
  - `apps/web/e2e/journeys/J12-client-portal.spec.ts` ("J12-core").
  - Both run on the F-04-T21 harness, with axe and INV-1 to INV-5 after every step.
  - A step whose screen or backend is still planned is `test.fixme`, with an `owner` annotation naming the epic, the task and its sprint end date.
  - The fixture adapter answers a portal persona's entry path with `portal.html`, because the fixture server is the firm's vite dev server.
- **Path filter (T28):** `abacus_tools.ci.paths` gains `journeys` and `JOURNEYS`, so the pull request job runs when the SPA, portal, UI library, journeys, harness or their config change.
- **CI (T28):**
  - `ci.yml`: a `journeys` job running `make journeys JOURNEY_ARGS=--trace=on`. It always uploads the report and traces (axe findings are report attachments). It joins the `stage-2` gate.
  - `e2e.yml`: a nightly `fullstack` job (`make dev`, `make seed-demo SNAPSHOT=E0 HOLDOUT=fairhaven_ebp`, `make journeys-full`) on the runner's own compose stack, with the same uploads.
  - `e2e.yml`: a `staging` job that runs only when the repository variable `STAGING_JOURNEYS` is `on`. It drives a browser at the hosted URL and does nothing else.
  - `nightly-red` covers the full-stack job too.
- **Makefile:** `JOURNEY_ARGS` is passed through to the two journey targets.
- **Migrations, flags, matrix, dependencies:** none. No secrets, and no AWS or WorkOS credentials.
- **Tests:**
  - `tests/unit/tools/test_paths.py`: new journeys cases, and the `main` output line;
  - `tests/unit/tools/test_journey_workflows.py`: the gate, the order on the runner's stack, staging off and inert, uploads, loopback-only database settings, and no `seed-staging` or `secrets.` in the journey workflows.
  - The two specs run in fixture mode.
- **Rollback:** revert the commit. The new jobs disappear and no data is touched.

## What changed
- **J02-audit-core**, walkable:
  - step 1 as Grace Holloway (`/clients`);
  - the INV-3 wall step as Lena Park (no Ashford Manufacturing Co., checked as out of scope).
- **J02-audit-core**, `test.fixme` with owners:
  - CLI-06 (P-07-T49, S11);
  - CLI-07 (P-07-T46, S10);
  - ENG-03 (P-07-T21, S6);
  - ENG-02b (P-07-T20, S6);
  - BND-01 (P-06-T16, S6): `binders.engine` is not on in E0 in fixtures or `make seed-demo`, so `/binders` shows the flag-off state;
  - BND-02 (P-06-T16, S6).
- **J12-core**, walkable:
  - step 1, POR-01a as Claire Feld on the portal entry, with no product name on the page;
  - steps 2–3, the emailed code (POR-01b) and Claire's to-dos (POR-02a, landed on main during this task). These are walkable in fixture mode. On the other projects they are fixme under P-08-T10 (the portal sign-in BFF).

  `fixtures/install-portal.ts` now answers `GET /v1/portal/home` with the persona's POR-02 home, so sign-in lands somewhere.
- **J12-core**, `test.fixme` with owners:
  - POR-03a (R-01-T06, S7);
  - the upload (R-01-T10 and R-01-T12, S9).
- **Fixture-mode run (`make journeys`):** 12 passed (the harness's 8, J02's 2, J12's 2) and 8 fixme.
- **CI:** as planned.

## Not done, and why
- **"Both specs run on staging by Jan 22":** there is no staging environment. The staging job exists and is off: the repository variable `STAGING_JOURNEYS` is unset. It also needs `ABACUS_STAGING_URL`, a registered hosted sign-in (real WorkOS persona users on the sink domain), and a read-only OIDC role for the sink bucket (Q-01-T47).
- **The full-stack variants** were not run locally. They need `make dev` and `make seed-demo` on Docker. The nightly job runs them.
- **`/clients` in E0** still answers with the earlier client list, because `clients.v2` is not turned on for the firm in E0. Step 1 walks what the route shows.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-207 | Journey skeletons: file names, fixme owners, the portal entry in fixture mode, E0 flags | no |
| DEC-208 | CI journey jobs: one path filter, traces always, staging off behind a repository variable, nothing hosted from a runner | no |

## Progress log
- 2026-10-23: built in one PR (PR B of the S6 F-04 batch). The fixture project passes (journeys and harness). The paths and workflow tests pass.
