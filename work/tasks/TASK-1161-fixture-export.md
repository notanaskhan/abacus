---
id: TASK-1161
title: make fixtures — fixture JSON exported from the Python scenario through the API, and the fixture vs seed-demo equivalence test (F-04-T31)
spec: SPEC-307
acceptance_criteria: [AC-1]  # F-04.21 (F-04 §3)
risk_zone: green
status: in-progress
epic: F-04
plan_key: F-04-T31
branch: s7-small-items-incidents
created: 2026-10-24
updated: 2026-10-27
---

## Objective
"Fixture JSON is exported per snapshot, matches seed-demo on MVP read paths and the interim ADR-085 exception is retired." F-04.21: `make fixtures` exports `apps/web/src/fixtures/seed/*.json` from the Python scenario at each named snapshot; the TS modules import the JSON; a test asserts fixture mode and `make seed-demo` + API return identical E0 data on the MVP read paths (clients, engagements, binders, requests, portal home).

## What was built
- `abacus_tools/synthetic/fixture_export.py` and `make fixtures SNAPSHOT=E0`: loads E0 (with `--slice portal`, the TS seed's portal minimum) into a throwaway Postgres container, reads the API in-process as the scenario personas under the snapshot clock, writes `seed/e0.<read>.json` with the scenario version, hash, snapshot, slices, persona and request.
- Exported reads: `GET /v1/firm/clients` (Grace Holloway, firm admin), `GET /v1/engagements` (Hannah Leclerc), Northwind's `GET /v1/engagements/{id}/request-items` (Hannah Leclerc), `GET /v1/binders?service=tax_returns&season=TY2025` (Daniel Reyes, the Feld engagement's partner) and `GET /v1/portal/home` (Claire Feld, through a portal session the exporter opens on `brightwaterhale.portal.localhost`).
- The exporter's `load()` sets the flags the reads stand behind (`binders.engine`, `portal.sign_in_v2`, `portal.home_v2`) and loads with `portal_base_domain`, so the portal host exists. The equivalence test loads through it.
- The loader now gives clients and entities the ids the TS seed uses (`client:<slug>`, `entity:<slug>:<entity>`) through optional ids on `organisations.create_client` and `client_with_entity`; before, every load drew new random client ids, so no export could be stable or match the TS seed (DEC-291).
- `tests/integration/test_f04t31_fixture_equivalence.py`: loads E0 in its own database and requires the committed files to equal seed-demo + API byte for byte.
- `apps/web/src/fixtures/seed/exported.ts` (typed JSON imports) and `exported.test.ts`: every row the API answers is served by fixture mode with the same values in every field fixture mode sets.

## What is left (why the row is partial)
- **Known divergences, pinned in `exported.test.ts`:** fixture mode lists all 28 engagements to every persona (the API lists Hannah her own one); it serves rows in the TS seed's order (CLI-01 featured clients first; handoff PBC order) where the API sorts by name and its own key, and `seed.test.ts` pins those orders; the TS seed names third-party portal people as client assignees on 11 Northwind items that the scenario's load leaves unassigned; it leaves optional request-item fields unset.
- **More known divergences, pinned in `exported.test.ts`:**
  - The Feld binder's `id` and `work_item_id` differ, because the TS seed derives them from the client slug and the load from scenario labels. Its `preparer_user_id` differs too (BND-01 reads KO; the load has none), and so does `allowed_actions`.
  - Claire's portal home differs from POR-02 a in every populated section. POR-02 reads the binder as 19 of 21 (SPEC-320 AC-15) where the load holds BND-02's 5 of 7.
  - The binders persona is Daniel Reyes, not Grace. The practice leader's `in_scope` reads nothing until practice lines load, and Grace's membership in the goldens is granted by hand.
- **Not retired:** the interim TS-seed exception stays recorded until fixture mode serves the exported JSON for every MVP read, which needs the screen tests that pin the TS seed's order and the persona filtering to move with it.

## Progress log
- 2026-10-24: exporter, three E0 exports, equivalence tests both sides, stable client ids. 3 backend equivalence tests, 4 vitest cases, scenario integration suites green (23 passed, 4 xfailed as before). A first export run before the engine was pointed at the throwaway database sent the loader's service writes to the default local database until it failed; the exporter now configures the engine first.
- 2026-10-27 (S10 gap build): binders index and portal home exported. The binders read is by Daniel Reyes; Margaret Okonkwo's practice-leader view was empty. The portal home is read by Claire Feld through a real portal sign-in, opened before the snapshot clock because challenges expire by the database's clock. The load sets `portal_base_domain` so the portal host is written, plus the read paths' flags. Web: `exported.ts` gains both reads; `exported.test.ts` gains 2 tests with pinned gaps (6 passed). The interim ADR-085 exception is still not retired: the binder ids, the POR-02 home and the TS seed's orders and persona filtering must move to the load first.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-291 | Export layout, personas, slices and the scenario's stable client ids are not fixed by F-04.21 | No |
