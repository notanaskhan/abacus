---
id: TASK-1221
title: Python scenario slice for POR-03, POR-04 and POR-14 through service APIs (R-01-T11)
spec: SPEC-323
acceptance_criteria: [AC-5]
risk_zone: amber
status: blocked
epic: R-01
plan_key: R-01-T11
branch: s8b-portal-ui
created: 2026-10-25
updated: 2026-10-25
---

## Objective
"make seed-demo loads every POR-03, POR-04 and POR-14 persona state idempotently and the fixture export matches it."

## Plan (amber zone)
- **Slice** `portal_pbc` in `backend/src/abacus_tools/synthetic/scenarios/brightwater_hale/portal_pbc.py`, opt-in like `portal` (`--slice portal_pbc`; `NEEDS = ("portal",)`, which brings `binders`); `build()` keeps its default, so SCENARIO_HASH does not move. Registered with `@register_slice`; `loader.SLICE_NEEDS` gains it.
- **Events, each through a service API in a unit of work under the named firm person** (the loader's `_branding_set` pattern), bootstrapped only where no service can be called by a loader (as `_portal_person_added` is, with the history row the service writes):
  - Feld (E0, Mon Sep 14): the five received rows' files and receipts as POR-03 a names them (`Claire_Feld_2025_W2_MercerHill.pdf` emailed Aug 3, `Jonah_Feld_2025_1099_Composite_Halvard.pdf` uploaded by Jonah Aug 5, `Claire_Feld_2025_1098_HudsonMutual.pdf` emailed Aug 3, `Feld_2025_Donations.pdf` uploaded by Claire Aug 7), the K-1 firm-provided; `Feld_1095C_2025.pdf` arriving by email at 9:12 and waiting in the Inbox (INB-02 files it: c2 is the after-state); synthetic bytes from `abacus_tools.synthetic.documents`, content-addressed through `evidence.api`.
  - The returned 2024 form as a holdout (`holdouts.py`): Claire's portal upload of `Feld_1095C_2024.pdf` and Kevin Osei's return with `wrong_year` and the client-visible note.
  - Northwind: Dana's own requests with their client titles (POR-03 i), the delegations to Keystone, Harborline, PayGrid and Summit through `requests.api` (the invitation-on-delegation subscriber makes Harborline's contact), Sam Ortiz's 9 Keystone items with 4 uploaded Sep 2 (POR-14 a), the bridge letter's guidance and two comments, the Harborline certification variant (POR-14 d).
- **Golden footings** `backend/tests/golden/scenario/brightwater_hale/test_portal_pbc_slice.py`: Intake 2 = POR-02 Upload 2 = POR-03 open 2; Keystone 4 of 9; Harborline 1 of 2; Dana's bands; replay idempotence (a second load writes nothing).
- **Fixture export**: `abacus_tools.synthetic.fixture_export` gains the portal-pbc reads for each persona, compared with `apps/web/src/fixtures/seed/portal-documents.ts` (a diff test, like F-04-T31's).
- **Integration**: `tests/integration/test_scenario_portal_pbc.py` loads the slice into the test database and reads each persona's binder, request and room through the routes.
- **Rollback**: the slice is opt-in; a local database is reset with `make migrate` from empty. Nothing runs against staging (`seed-staging` is not changed here).

## Why it is blocked
DEC-348 (open): the sources disagree, and building the slice as written would invent rows, which the constitution forbids (frontend rule 5, non-negotiable 16's seed rule):
1. The Feld binder is 21 requests with 19 done in POR-02, POR-03 and TAX-03, but only 7 request titles exist anywhere (BND-02a's "5 of 7" and the `binders` slice). The other 14 have no source.
2. "Brightwater Hale sorted 37 of your files" names none of the 37.
3. Northwind's delegations (CLI-04: 10 / 9 / 2 / 2 / 1) disagree with AUD-03's owner column (Dana 9, Harborline 4, Keystone 7, PayGrid 3, Summit 1); P-08-T18 took Keystone's 9 by category, two of them Harborline-owned.
4. POR-14's Keystone room names two requests that are not among AUD-03's 24 (contribution remittance report, plan expense invoices) and omits two that are (certified trust report, summary of net trust assets).
5. POR-14 d's two Harborline items are not on AUD-03's list.
6. POR-03 i's "Plan documents 0 of 1" disagrees with AUD-03, where Dana owns three received plan documents.

DEC-348 carries a proposed resolution. The named Feld subset (the five receipts, the 9:12 email, the 2024 holdout) is buildable without inventing data; it was not started here, because it needs the loader to store evidence bytes through `evidence.api` (a capability the loader does not have yet: it bootstraps no files today) and is best built once with the rest of the slice, after DEC-348.

## Progress log
- 2026-10-25: plan written; blocked on DEC-348 (sources disagree; see above). No code. The TS fixtures (R-01-T05) stay the source for the screens until then.
