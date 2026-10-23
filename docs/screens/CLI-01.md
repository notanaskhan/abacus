# CLI-01 · Clients index

| Field | Value |
|---|---|
| Route and params | `/clients` (P-07 §5). Search params `kind`, `office`, `partner`, `service_line`, `status`, `q`, `cursor`; "Import…" opens `/clients/new?mode=import`. Artboards: `/components/screens/CLI-01?st=a…f` |
| Template and host frame | T1 `IndexList` (FilterBar, single Pane, ledger DataTable; F-05-T28) · `Wave 1 - Module Shells.dc.html#cli01` |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/CLI-01 Clients index/` (README.md, spec.md; spec-alt.md is byte-identical; no revision) · HANDOFF_VERSION 2026-10-21 |
| Epic and tasks | P-07 · contract P-07-T01 · fixtures and scenarios P-07-T11 · screen P-07-T12 · read model P-07-T08 · parity lock P-07-T63 |
| Manifest status | fixture (`routes/manifest/cli.ts`, path `/clients`, `navArea: "Clients"`; P-07-T12). Live when P-07-T08 serves `GET /v1/clients` and `clients.v2` turns on |

Code (P-07-T11, T12): `src/routes/firm/clients.tsx`, `src/domain/clients/{index.ts, queries.ts, messages.ts}`, `src/screens/CLI-01/{index.tsx, scenarios.ts, copy.ts, CLI-01.test.tsx}`, `src/fixtures/{handlers/clients.ts, handlers/engagements.ts, seed/client-rows.ts, scenarios/CLI-01.ts, clients.foot.test.ts}`, `e2e/screens/CLI-01.spec.ts`. Flag `clients.v2`: on, CLI-01; off, the SPEC-303 legacy list until P-07-T58 retires it (see Deviations).

## States

6 artboards in the handoff, 6 built here, all live in production at P-07's exit.

| Artboard | Viewer (persona) | Clock | Snapshot | Data condition that produces it | Status |
|---|---|---|---|---|---|
| a | grace-holloway (Grace Holloway, Firm Admin) | Mon Sep 14, 2026, 9:24 AM CT | E0 | Status │ Active; the 184 clients, first page of 16 by newest last client activity; `next_cursor` set, so "Load more" shows | built · fixture (T12) |
| b | grace-holloway | same | E0 | Service line │ Audit: Northwind, Granite Peak, Lakeshore; `total` 3 | built · fixture (T12) |
| c | lena-park (Lena Park, seasonal preparer) | same | E0 | An active wall Lena ↔ Ashford Manufacturing Co.: Ashford is absent from rows and `total`, with no footer, count or gap (DEC-43) | built · fixture (T12) |
| d | grace-holloway | same | E0 | `q=Schwab` matches no client, entity or contact | built · fixture (T12) |
| e | grace-holloway | same | E0 | `GET /v1/clients` never answers (`never()` handler) | built · fixture (T12) |
| f | grace-holloway | same | empty-firm override | The firm has no clients (first day) | built · fixture (T12) |

Not-allowed: a walled client is absent everywhere and a guessed `/clients/<id>` answers 404 and renders not-found; nothing says a client is hidden (INV-3, DEC-43). Error: F-05's ViewState error row (C-20). A firm role without `client.read` gets the C-20 not-allowed pane. Flag off (`clients.v2`): the flag-off ViewState.

## API
| Read or write | Endpoint | Shape | Matrix action | allowed_actions and read-only reasons per role |
|---|---|---|---|---|
| read | `GET /v1/clients?kind=&office_id=&partner_id=&service_line=&status=&q=&sort=&cursor=&limit=` | P-36 list envelope `{items, next_cursor, total, counts, facets}`; `total` exact (DEC-47); no `hidden_by_wall` field anywhere; `q` is a list parameter over the resource's own columns and is never logged | `client.read` | every firm role (metadata only; walls applied in `visible(scope=client)`); agent and client principals deny |
| write | — (row "···" Copy client ID is local; "+ New client" and "Import…" open CLI-06) | — | `client.intake` · `client_import.run` decide whether the buttons render | firm_admin, partner, manager; hidden for other roles (`useCan`) |

## Status
No client status object exists yet in `docs/product/status-vocabulary.yaml`; P-07-T03 adds `client` (Prospect · Active · Inactive · Former, DEC-62) and the portal rollup words (DF-31). Until it lands the screen renders only the handoff words: Status chip "Active"; Portal pill "Active" (green-tint), "Invited" (amber), "Not invited" (neutral).

## Copy
Copy keys live in `screens/CLI-01/copy.ts`; every string below is verbatim from spec.md unless the Deviations table says otherwise.

| Key | String |
|---|---|
| `filters.type` | "Type │ All" |
| `filters.office` | "Office │ All offices" |
| `filters.partner` | "Partner │ All" |
| `filters.serviceLine` | "Service line │ All" (b: "Service line │ Audit") |
| `filters.status` | "Status │ Active" (the active chip) |
| `pane.title` | "Clients" |
| `pane.search` | "Search clients, entities, contacts" |
| `pane.count` | "{total} clients" (a: "184 clients"; DEC-47, see Deviations) |
| `pane.showing` | "Showing {n}" (b: "Showing 3") |
| `pane.import` | "Import…" |
| `pane.newClient` | "+ New client" |
| `columns` | "Client" · "Type" · "Entities" · "Services" · "Office" · "Partner" · "Portal" · "Open requests" · "Last activity" |
| `tag.attest` | "Attest" |
| `services` | "Tax" · "Audit" · "CAS" · "Advisory" |
| `portal` | "Active" · "Invited" · "Not invited" |
| `openRequests.none` | "—" |
| `openRequests.binderDraft` | "Binder draft" |
| `loadMore` | "Load more" |
| `empty.filtered` | "No clients match '{q}'." (d: "No clients match 'Schwab'.") |
| `empty.clear` | "Clear filters" |
| `empty.firm.title` | "No clients yet." |
| `empty.firm.body` | "Add a client or import your client list from CCH Axcess Tax or a CSV." |
| `menu` | "Open" · "Message" · "New engagement" · "Copy client ID" |
| `toast.copied` | "Client ID copied" |

Row text (client names, sub-lines, types, offices, partner initials, last-activity lines) is data from the Brightwater Hale seed (`src/fixtures/seed/clients.ts`, spec.md ROWS 1–16), never from `copy.ts`.

## Links
| From | To (manifest builder) | Planned or live |
|---|---|---|
| A row ("Opens CLI-02 · Jonah & Claire Feld") | CLI-02 `to.CLI02({ clientId })` | planned (P-07-T19 builds it) |
| A Services tag ("Opens ENG-01 · Tax engagements for Jonah & Claire Feld") | ENG-01 `to.ENG01()` with `client_id` and `line` | planned (P-07-T27) |
| Portal pill ("Opens CLI-04 · contacts and portal access") | CLI-04 | planned (P-07-T33) |
| Open requests cell ("Opens BND-02 · open binder") | BND-02 `to.BND02({ binderId })` | planned (P-06-T12) |
| "+ New client" | CLI-06 (single) | planned (P-07-T49) |
| "Import…" ("Opens CLI-06 in bulk import mode") | CLI-06 with `?mode=import` | planned (P-07-T54) |
| Row "···" New engagement | ENG-03 prefilled with the client | planned (P-07-T21) |
| Row "···" Message | INB-04 | planned (N-03); the menu item is hidden in production until N-03 registers it |
| Row "···" Open · Copy client ID | the row's record · clipboard and toast (local) | in-screen |

Inbound: SHL-01 nav "Clients", SHL-02, CLI-02 "‹ All Clients", CLI-04, FIL-01, TPL-14. All targets are manifest IDs that `link-contract.test.ts` knows.

## Acceptance
- CLI-01 acceptance: split filter chips with the amber active chip; one white pane with 10-px gutters and a 46-px header with a centered title.
- CLI-01 acceptance: the 16 rows are exactly the blueprint §9.3 clients, with offices and engagements as seeded.
- CLI-01 acceptance: Northwind's 13 open requests = 24 − 11 received; Ridgeline 5 (its five waiting-on-client issues); Feld 2 (two open portal requests); Copperleaf 2 (9 August close requests − 7 received; its 3 open transaction questions are not requests).
- CLI-01 acceptance: entity counts Northwind 2, Granite Peak 2, Thornbury 2; every other client 1.
- CLI-01 acceptance: Attest tags appear only on Northwind, Granite Peak and Lakeshore; Copperleaf and Juniper & Oak are non-attest CAS.
- CLI-01 acceptance: the Thornbury portal reads "Invited", not Active.
- CLI-01 acceptance: no TINs anywhere in the list; status and portal words are from the approved vocabulary.
- P-07 §3.1 Story 1.2: for Lena Park the response has the same shape as for a firm without Ashford, `total` excludes it, and no footer, count, gap or "hidden" text renders (c test).
- P-07 §3.1 Story 1.1: "Load more" appends the next keyset page; there are no page numbers.

## Figures
| Figure | Foots | Proven by |
|---|---|---|
| Header (a) | 184 clients at E0 (DEC-47): 16 named + 66 roster + 102 filler | `fixtures/seed.test.ts` (F-04); `fixtures/clients.foot.test.ts` (P-07-T11) |
| Rows (a) | 16 rows by newest last activity; "Load more" with no total | P-07-T11 scenario test |
| Northwind open requests | 13 = 24 − 11 | `fixtures/clients.foot.test.ts`, computed from the seed's PBC list |
| Ridgeline · Feld · Copperleaf | 5 · 2 · 2 (2 = 9 − 7) | same |
| Granite Peak | "Binder draft" (only a draft binder exists; draft requests excluded) | same |
| Entities | Northwind 2, Granite Peak 2, Thornbury 2, others 1 | same |
| Filtered (b) | Northwind + Granite Peak + Lakeshore first; "Showing 25" on the seed (DV-3; the handoff's "Showing 3" counted its 16-row sample) | `fixtures/clients.foot.test.ts`; scenario test |
| Restricted (c) | Ashford absent from rows; `total` 183 = 184 − 1, the same shape as a firm without Ashford (the handoff caption read "15 most recently active" over the 15 named rows left) | scenario test and P-07-T13 |
| Loading (e) | 8 skeleton rows | scenario test |

## AVOID
Gradients in product UI, emoji, saturated blue links, heavy shadows, invented colors, lorem ipsum, zebra rows, avatars or colored initials, full TINs (never show TINs in the index), card-per-client layouts, the words Accrual/Arc/ACME. From P-07 §5: "hidden by an ethical wall" or any wall count, weights 600/700, "task" for a to-do.

## Deviations
| ID | What differs from the handoff | Why | Decision recorded |
|---|---|---|---|
| DEC-43 | c drops the footer "1 client hidden by an ethical wall"; nothing replaces it, for admins too | A count leaks existence; 404 semantics everywhere (OQ-1: CLI-01c joins DF-14) | DEC-43, DF-14; P-07 OQ-1 decided in DEC-138 |
| DEC-47 | The pane-header caption reads "{total} clients" ("184 clients" at E0) instead of "16 most recently active" | The header carries the firm's exact client count | DEC-47; P-07 §2.1 amended copy |
| DEC-62 | The Thornbury row reads client "Walter Thornbury" (2 entities: the decedent and the estate) where spec row 9 reads "Estate of Walter Thornbury" | A client's display name is its own field and never follows an entity | DEC-62 |
| — | Row "···" Message (INB-04) is hidden in production until N-03 registers it | Planned targets are hidden in production (chapter 04 §2.1 rule 4) | P-07 §2.1 |
| DV-1 (T12) | Every outbound target (CLI-02 row open, CLI-04 portal pill, ENG-01 service tags, BND-02 open requests, CLI-06 "+ New client" and "Import…", ENG-03 and INB-04 in the row menu) is planned: the controls are hidden in production and drawn disabled with their "Opens …" hint in dev, fixture and gallery builds (`app-core/planned.ts`). Rows, tags and pills are not links until their targets are built | Chapter 04 §2.1 rule 4 | P-07-T12 (TASK-944) |
| DV-2 (T12) | `clients.v2` off keeps SPEC-303's legacy list at `/clients` instead of F-05's flag-off state | The flag defaults off in every firm; the flag-off state would take a working list away before CLI-01 is live. P-07-T58 retires the legacy list and the fallback becomes the flag-off state | P-07-T12 (TASK-944) |
| DV-3 (T12) | b reads "Showing 25", not "Showing 3": Service line │ Audit over the seed's 184 clients is the 3 named audit clients (first, newest activity) and the 22 §9.7 roster audits | The handoff's count was taken over its 16-row sample; the seed is not trimmed (as DEC-138 OQ-5 does for ENG-01) | P-07-T12; parity masks the count text |
| DV-4 (T12) | "+ New client" and "Import…" render for `client.intake` holders | `client_import.run` is not an action in the matrix yet (`actions.gen.ts`); CLI-06's bulk import task adds it | P-07-T12 |

## Parity
| Artboard | Tier (A/B/C/D) | Diff % | Notes |
|---|---|---|---|
| a, b, d, f | C (locked before M8) | not run (axe 0 serious in `e2e/screens/CLI-01.spec.ts`; parity reported by P-07-T63) | P0 lock at Tier C (P-07 §5 Parity, T63); mask the header count text if the seed differs (OQ-5) |
| c | C (report) | not run | mask the footer region (DEC-43) |
| e | C (report) | not run | mask the skeleton pulse |
| host | D | — | toolbar 46, filter bar 50, pane header 46 with a 14.5/500 title, rows 44, th 30, pills 21/22/18 |

## Open gaps
- **Type pill (T12).** `ClientRowOut.kind` is the five-value client kind (`household`, `business`, `plan_sponsor`, `nonprofit`, `trust_family`); the handoff's type pills name the entity's tax form for businesses ("S corporation", "C corporation", "Partnership", "Single-member LLC") and "Individual" and "Estate" for people. The screen words the kind (`domain/clients/messages.ts`: Household, Business, Plan sponsor, Exempt org, Trust) until the read model carries the primary entity's form (a `primary_entity_form` field, P-07-T08 or a later contract change). Parity masks the Type column text.
- **Last activity line (T12).** The row carries `last_activity_at` and `last_activity_event_type`, not the actor or object, so the line reads "9:12 AM · Documents uploaded" where the handoff reads "9:12 AM · Claire Feld emailed 2 forms". The event-type wording table is `ACTIVITY_WORDS` in `domain/clients/messages.ts` (an event type without words shows the time alone); the full line needs a client-safe `last_activity_summary` from the read model. These words are not handoff copy.
- **Thornbury's name (T11).** The TS seed and the Python golden file (`backend/tests/golden/scenario/brightwater_hale/clients.json`) still name the client "Estate of Walter Thornbury"; the fixture read model shows the client's own name "Walter Thornbury" (DEC-62, `CLIENT_DISPLAY_NAME` in `fixtures/seed/client-rows.ts`). The seed rename is a backend scenario change (F-04-T31 or P-07-T08).
- **Search over contacts (T11).** The fixture `q` matches the client's name, descriptor and entity names; the seed has no per-client contact list outside the three portal engagements, so contact matches arrive with the read model.
- Row 9's last-activity line "Sep 11 · Acceptance pre-screen drafted" names an agent pre-screen, which v1 does not run (DEC-64, P-07 §2.3). The fixture keeps the handoff line for parity; production shows the seed's latest real event for Thornbury.
- The handoff's d copy is "No clients match 'Schwab'."; P-07 §1 summarises it as "No clients". The handoff wins (verbatim rule).
- Personas `grace-holloway` and `lena-park` exist in the F-04 seed; the empty-firm override (f) is a scenario-local handler.
