---
id: TASK-386
title: Route registry from the handoff link graph - seed-manifest.mjs, manifests, to.ID() builders, link-contract test (F-04-T14)
spec: SPEC-307
acceptance_criteria: [AC-8]
risk_zone: green
status: done
epic: F-04
plan_key: F-04-T14
branch: f04-t14-route-registry
created: 2026-10-22
updated: 2026-10-22
---

## Objective
"Generator adds new IDs only and link-contract.test.ts enforces rules 1-4 against
HANDOFF_VERSION." (F-04 section 3.7, F-04.29; chapter 04 section 2.6; G-B03)

## What changed
- `apps/web/scripts/seed-manifest.mjs` (`pnpm -C apps/web routes:seed`): reads
  `$ACCRUED_HANDOFF_DIR/handoff/screen-index.json`, refuses to run unless
  `docs/design/HANDOFF_VERSION` pins its sha256, adds a manifest entry for each new screen ID
  (status `planned`, path `null`, `entry: true` when no link targets it) above a marker line in
  `src/routes/manifest/<module>.ts` and never edits an existing entry. It rewrites
  `manifest/index.ts` (gathers the modules) and `src/routes/handoff-links.json` (one link per line:
  source, target, artboard, type and tooltip; the record-key links; links to IDs the index does not
  list, CLI-03 and WB-05; the 51 never-targeted screens). Seeded output is already
  prettier-formatted; the JSON is in `.prettierignore`.
- `docs/design/HANDOFF_VERSION` now reads `2026-10-21 sha256:<screen-index hash>` (9308819dd3f3).
- 29 manifest modules, 278 screens. Already-routed legacy screens got their path by hand
  (CLI-01 `/clients`, CLI-02 `/clients/$clientId`, ENG-02 `/engagements/$engagementId`, KNW-01
  `/knowledge`), still `planned` because none is built from the handoff yet.
- `src/routes/to.ts`: typed `to.<ID>()` builders (`to.CLI02({ clientId })` gives a `<Link>`'s
  `to` and `params`), only for entries with a path, so linking to an unrouted screen does not
  compile. ESLint bans string `to` in `src/screens/**`.
- `src/routes/records.ts`: record-key routes for AJE, BH and SURL (paths null until their screens).
- `src/routes/link-contract.test.ts`: rules 1-4, the HANDOFF_VERSION pin (and the local
  handoff's hash when it is on the machine), manifest and handoff hold the same IDs, and the
  generator's core on fixtures (existing entries untouched, idempotent, marker, version refusal,
  link-graph classification). Rule 1 holds vacuously while screens are planned; its checker is
  tested on a synthetic manifest.

## Decisions
- Links come from screen entries only; template, component and journey entries are not routes.
- A link target that is no indexed screen is a record key when its prefix is no screen module
  (AJE-06, BH-26, SURL-03), otherwise an unindexed screen (listed, not invented).
- Rule 2 also requires portal (POR) paths to sit outside the firm workspace route.
- The source screen's folder for rule 1 is `src/screens/<ID>` unless the entry sets `folder`.

## Progress log
- 2026-10-22: built. Ran tsc, eslint, prettier on the touched files and the new vitest file
  (17 passed). Full suites run in the batch's end-of-run CI (S3 batch rule).
