---
id: TASK-1221
title: Python scenario slice for POR-03, POR-04 and POR-14 through service APIs (R-01-T11)
spec: SPEC-323
acceptance_criteria: [AC-5]
risk_zone: amber
status: in-review
epic: R-01
plan_key: R-01-T11
branch: s10-r01t11-portal-slice
created: 2026-10-25
updated: 2026-10-27
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

## As built (2026-10-27, under DEC-348)
DEC-348 was decided 2026-10-27 (Ayush Bhatia: the proposed option). The plan above was written before it; what landed is narrower, because most of what it lists is either unnamed by any source or refused by a service the loader must go through.

**Built** (`backend/src/abacus_tools/synthetic/scenarios/brightwater_hale/portal_pbc.py`, `--slice portal_pbc`, NEEDS `binders` and `portal`; `build()` unchanged, so SCENARIO_HASH does not move):
- Dana's client titles (POR-03 i) on four of AUD-03's open Dana rows, through `requests.api.update_item` (newly exported from `lifecycle`, with `ItemPatch`) as Marcus Delaney at the list's publish (Sep 1): "W-3 Form" → "W-3 for 2025", "Opt-Out Elections" → "Opt-out elections — auto-enrolled employees", "Pay Rate Authorizations" → "Pay rate authorizations", "Participant Complaints Log and Support" → "Participant complaints log and support". AUD-03 keeps its 24 rows, totals and `description`s. "IRS opinion letter on the pre-approved plan document" is the same on both screens.
- Goldens: `backend/tests/golden/scenario/brightwater_hale/portal_pbc.yaml`, typed from POR-03, AUD-03, POR-14 and SHL-14, held to the loaded tenant by `backend/tests/integration/test_r01t11_portal_pbc_goldens.py` (Feld 5 of 7 with the 1095-C and estimates open; Dana's titles and the W-3's Sep 18; AUD-03 24 / 11 / 1 / 12 with descriptions kept; a second load replays nothing; Granite Peak's SURL Draft at the 2026-10-01 snapshot and absent at E0).
- `loader.SLICE_NEEDS` gains `portal_pbc`. `expand_slices` expands one level, so the slice names `binders` itself.

**Gaps** (each a strict xfail in the golden test where the source gives a figure; returned to the handoff under DEC-348):
1. "Employee census file — 2025" (POR-03 i): AUD-03's row is received, and `update_item` refuses a received request (`request_closed`). The title stays "Employee Census File". `test_danas_census_row_reads_the_portal_title`.
2. Claire's 9:12 AM email, `Feld_1095C_2025.pdf` (POR-03 c, c2; INB-02): the Feld TY2025 engagement carries no client acceptance (`binders` bootstraps the engagement; no source gives Feld's acceptance), so `evidence.api`'s client-data gate (SPEC-025 AC-7) refuses any client file on it with `acceptance`. Tried through `add_to_inbox` as Claire; refused. Also, the Inbox has no email channel until N-01. `test_claires_9_12_email_waits_in_the_feld_inbox`.
3. The Feld received rows' files (W-2 and 1098 "Received by email Aug 3", Jonah's 1099 Aug 5, Claire's donations Aug 7): the same gate; and Jonah Feld has no portal sign-in in any slice.
4. The returned 2024 form (POR-03 g, POR-04 d, "holdout"): Kevin Osei's return is a person's review decision; `evidence.decide` runs only while that person serves a request (ADR-005, REVIEW-001), so no loader can take it, and bootstrapping a person's decision is what ADR-005 forbids. No holdout was added.
5. Delegations to Keystone, Harborline, PayGrid and Summit (POR-03 i's note): `delegate_item` needs a contact who is a portal user. Harborline, PayGrid and Summit exist only as organisation contacts (`acceptance` slice) with no named person, and Sam Ortiz's invitation is pending at E0 (POR-01d). So no request is delegated, and Dana's live binder lists every client-visible Northwind request, not only her own. `test_por03i_names_the_four_organisations_requests_went_to`.
6. POR-14 a, Keystone "4 of 9" at E0: it disagrees with POR-01d (Sam invited, not signed in, at E0) and with AUD-03's statuses (6 of Keystone's 9 are received or uploaded). `test_por14a_keystone_room_reads_4_of_9`. POR-14 d (Harborline's certification contact and two items not on AUD-03's list) is DEC-348 (5).
7. POR-03 i's binder title "PY2025 Audit requests": the PBC list has no name column the loader can set through a service.
8. POR-02 "19 of 21 · 37 sorted": DEC-348 (1), (2).

**Not changed:** `make fixtures` exports the `portal` slice at E0 (`fixture_export.SLICES`), so no exported fixture moves. The TS seed already reads POR-03 i's titles.

## Progress log
- 2026-10-25: plan written; blocked on DEC-348 (sources disagree; see above). No code. The TS fixtures (R-01-T05) stay the source for the screens until then.
- 2026-10-27: DEC-348 decided (the proposed option); built the slice on its terms in worktree `abacus-r01t11` (PR "R-01-T11 + P-06-T08: portal PBC slice and Granite Peak SURL", held for the batch). Seven gaps recorded above; four are strict xfails in `test_r01t11_portal_pbc_goldens.py`. Mistake on the way: `NEEDS = ("portal",)` loaded without `binders`, because `expand_slices` expands one level. The slice now names both. A recursive `expand_slices` would stop this recurring.

