# ENG-01 · Engagements index

| Field | Value |
|---|---|
| Route and params | `/engagements` (P-07 §5). Search params `line` (all · tax · audit · cas · advisory), `status` (a tile), `office`, `partner`, `letter`, `next_due`, `period`, `client`, `q`, `cursor`. Artboards: `/components/screens/ENG-01?st=a…e` |
| Template and host frame | T1 `IndexList` (Segmented, FilterBar, StatusTileRow, ledger DataTable; F-05-T28) · `Wave 1 - Module Shells.dc.html#eng01` |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/ENG-01 Engagements index/` (README.md, spec.md; no revision) · HANDOFF_VERSION 2026-10-21 |
| Epic and tasks | P-07 · contract P-07-T01 · fixtures P-07-T11 · read model P-07-T15 · screen P-07-T27 · parity lock P-07-T63 |
| Manifest status | planned (`routes/manifest/eng.ts`, path `/engagements`, `navArea: "Engagements"`) |

Code to come (P-07 §5): `src/routes/firm/engagements.tsx`, `src/domain/engagements/{index.ts, queries.ts, messages.ts}`, `src/screens/ENG-01/{index.tsx, scenarios.ts, copy.ts, ENG-01.test.tsx}`. Flag `engagements.v2`.

## States

5 artboards in the handoff, 5 built here, all live in production at P-07's exit.

| Artboard | Viewer (persona) | Clock | Snapshot | Data condition that produces it | Status |
|---|---|---|---|---|---|
| a | margaret-okonkwo (Margaret Okonkwo, Managing Partner) | Mon Sep 14, 2026, 9:24 AM CT (assumed: README says no frame states a time) | E0 | All service lines, period Current: 275 engagements; first 17 rows, past due first, then by next deadline | built · live (T27) |
| b | margaret-okonkwo | same | E0 | Letter │ Not signed with the Accepted tile selected: the 4 Accepted engagements without a recorded letter (rows 4, 6, 7, 9); the Prospect estate engagement is excluded | built · live (T27) |
| c | margaret-okonkwo | same | E0 | Segment Advisory: 1 row (Ridgeline cost segregation & §754 analysis); tiles recount to Accepted 1, all others 0 | built · live (T27) |
| d | margaret-okonkwo | same | E0 | `q=Harbor Lane` matches nothing | built · live (T27) |
| e | margaret-okonkwo | same | E0 | `GET /v1/engagements` never answers (`never()` handler) | built · live (T27) |

Not-allowed: a walled engagement is absent from rows, tiles, segments and totals; a guessed `/engagements/<id>` answers 404 (INV-3, DEC-43). Error: the ViewState error frame. Flag off (`engagements.v2`): the flag-off ViewState.

## API
| Read or write | Endpoint | Shape | Matrix action | allowed_actions and read-only reasons per role |
|---|---|---|---|---|
| read | `GET /v1/engagements?service_line=&status=&tile=&office_id=&partner_id=&letter=&next_due=&period=&client_id=&q=&cursor=` | P-36 envelope `{items, next_cursor, total, counts, facets}`; `counts.status` (minus the selected tile) feeds the tiles and `facets.service_line` the segments, both from one grouped query over the same `visible()` predicate; per row: letter summary, partner, next due with tone, work-item sub-line from its kind provider | `engagement.read_metadata` | every firm engagement role, practice leader `in_scope`, firm admin (metadata); agent and client principals deny |
| write | — ("+ New engagement" opens ENG-03) | — | `engagement.create` decides whether the button renders | partner, manager, and seniors by `firm_setting(seniors_can_create)` (DEC-38); agent never |

## Status
`engagement` (`status-vocabulary.yaml`): `prospect` Prospect (neutral) · `accepted` Accepted (neutral) · `contracted` Letter signed (green-tint) · `active` Active (state) · `on_hold` On hold (muted) · `delivered` Delivered (green) · `archived` Archived (soon, Lock 11). `declined` never shows as a tile. Work-item sub-lines use their own objects' words ("In review · Partner", "Scoping", "Processing", "Planning", "Gathering"…).

## Copy
Copy keys live in `screens/ENG-01/copy.ts`; strings verbatim from spec.md.

| Key | String |
|---|---|
| `segments` | "All" · "Tax" · "Audit" · "CAS" · "Advisory" (counts are data: 275 · 224 · 27 · 23 · 1) |
| `filters.office` | "Office │ All offices" |
| `filters.partner` | "Partner │ All" |
| `filters.letter` | "Letter │ Any" (b: "Letter │ Not signed") |
| `filters.nextDue` | "Next due │ Any" |
| `filters.period` | "Period │ Current" |
| `tiles` | "Prospect" · "Accepted" · "Letter signed" · "Active" · "On hold" · "Delivered" · "Archived" |
| `summary` | "{total} engagements · {prospect} prospect · {awaiting} awaiting a signed letter · {pastDue} past due" (a: "275 engagements · 1 prospect · 4 awaiting a signed letter · 2 past due") |
| `pane.title` | "Engagements" |
| `pane.search` | "Search engagements" |
| `pane.showing` | "Showing {n} of {total}" (a: "Showing 17 of 275"; b: "Showing 4 of 4") |
| `pane.export` | "Export" (hidden; cut until P-11) |
| `pane.newEngagement` | "+ New engagement" |
| `columns` | "Engagement" · "Client" · "Type" · "Period" · "Office" · "Partner" · "Status" · "Work items" · "Letter" · "Next due" |
| `letter.signed` | "✓ Signed {date}" |
| `letter.sent` | "Sent {date} · {signed} of {signers}" |
| `letter.viewed` | "Viewed {date} · {signed} of {signers}" |
| `letter.partial` | "{signed} of {signers} signed" |
| `letter.none` | "—" |
| `due.pastDue` | "{n} days past due" |
| `due.days` | "{n} days" · "1 day" |
| `banner.g3` (b) | "Portal requests and billing stay held until the letter is signed (G3)." |
| `empty.filtered` (d) | "No engagements match '{q}'." ("No engagements match 'Harbor Lane'.") |
| `empty.clear` (d) | "Clear filters" |
| `prospect.banner` (opens ENG-02) | "Acceptance pending — {partner} · Open acceptance ›" |

Row text (engagement names, clients, types, periods, sub-lines, letter dates and next-due sub-lines such as "Aug close · 4 days past due", "§754 election deadline", "Report target", "Letter due", "Respond by", "Form 706 · 49 days", "Opens when the letter is signed") is seed data from spec.md ROWS 1–17, never `copy.ts`. Partner cells are initials; their tooltip names come from the people seed.

## Links
| From | To (manifest builder) | Planned or live |
|---|---|---|
| A row ("Opens ENG-02 · Copperleaf 2026 Close"); the Prospect row opens ENG-02 with the pre-acceptance banner | ENG-02 `to.ENG02({ engagementId })` | planned (P-07-T20, T28) |
| "+ New engagement" ("Opens ENG-03 · new engagement wizard") | ENG-03 | planned (P-07-T21) |
| Work-items sub-line of a close ("Opens CLS-02 · August close") | CLS-02 | planned (C-01); plain text until then |
| Work-items sub-line of a return ("Opens TAX-02 · return overview") | TAX-02 | planned (T-02) |
| Work-items sub-line of an audit or review ("Opens AUD-02 · audit cockpit") | AUD-02 | planned (A-01) |
| Work-items sub-line of a notice ("Opens NOT-02 · notice workspace") | NOT-02 | planned (N-04) |
| Work-items sub-line of a project ("Opens PRJ-01 · project workspace") | PRJ-01 | planned (T-09) |
| Letter cell, sent letter ("Opens SIG-01 · signed envelope and evidence") | SIG-01 | planned (N-02); until then the cell opens ENG-02's Letter & terms card |
| Letter cell, draft letter | ENG-04 | planned (N-02); until then ENG-02's Letter & terms card |
| Prospect banner "Open acceptance ›" (inside ENG-02) | CLI-07 | planned (P-07-T46) |
| "Season setup…" | ENG-07 | planned (T-08); hidden in production |
| A tile; a segment; filter chips; Partner hover popover | the list's own search params (local) | in-screen |

Inbound: SHL-01 nav "Engagements", SHL-02, CLI-01 Services tag, CLI-02 Engagements tab, ENG-02 "‹ All Engagements", AUD-02, ENG-04, ENG-10, ENG-12, KNW-01, TPL-21, HOME-01. All targets are manifest IDs that `link-contract.test.ts` knows.

## Acceptance
- ENG-01 acceptance: same toolbar as close-overview, except Home comes first, "Workbench" replaces Arc, the pill reads "Brightwater Hale", and Engagements is the active item.
- ENG-01 acceptance: segment counts foot: 224 + 27 + 23 + 1 = 275; the seven tiles also sum to 275 (1 + 4 + 0 + 128 + 0 + 140 + 2); the Accepted tile (4) equals the four letters out (E11–E14); the Prospect tile (1) is the Estate of Walter Thornbury engagement.
- ENG-01 acceptance: status words come only from §3.3.1 (Prospect, Accepted, Active, Delivered, Archived); work-item sub-lines use the work item's own vocabulary.
- ENG-01 acceptance: days to deadline are red ink at ≤ 7 days, amber at ≤ 30, ink-2 beyond; Copperleaf reads "4 days past due" and Bluebird "2 days past due", so the summary reads "2 past due".
- ENG-01 acceptance: one white pane on #F8F8F6 with a 46px header and a centered 14.5/500 title; rows hairline-separated, no zebra stripes.
- ENG-01 acceptance: no Active audit, close, return or project lacks a signed letter; the unsigned ones are all Accepted, except the Prospect estate engagement, which has no letter ("—") and no open work item until G1 and G3.
- P-07 §3.6 Story 6.1: tiles and segments are computed by one grouped query over the same `visible()` predicate and sum to the header total in every scenario; a walled engagement is absent from rows, tiles and totals.

## Figures
| Figure | Foots | Proven by |
|---|---|---|
| Segments (a) | 224 + 27 + 23 + 1 = 275 | P-07-T11 seed footing test |
| Tiles (a) | 1 + 4 + 0 + 128 + 0 + 140 + 2 = 275 | same |
| Summary (a) | 1 prospect = Prospect tile; 4 awaiting a signed letter = Accepted tile; 2 past due = Copperleaf + Bluebird | same |
| Letter not signed (b) | "Showing 4 of 4" = rows 4, 6, 7, 9 = Accepted tile | scenario test |
| Advisory (c) | 1 row; tiles Accepted 1, others 0 | scenario test |
| Days | Ridgeline 1065 "1 day" (Sep 15); Calloway "16 days" (Sep 30); Feld, Shah, Thornbury "31 days" (Oct 15); estate "Form 706 · 49 days" (Nov 2) | clock test on the demo clock |
| Loading (e) | skeleton tile counts and 8 skeleton rows | scenario test |

## AVOID
Gradients in product UI, emoji, saturated blue SaaS accents, heavy shadows, invented colors, lorem ipsum, zebra rows, vertical rules, weights 600/700, "$" in table cells, the words Accrual/Arc/ACME. From P-07 §5: internal engagement numbers in chrome, "task" for a to-do.

## Deviations
| ID | What differs from the handoff | Why | Decision recorded |
|---|---|---|---|
| — | "Export" is hidden | Needs P-11's document writer (cut) | P-07 §2.3 |
| — | The Letter cell opens ENG-02's Letter & terms record card instead of ENG-04 or SIG-01 | Interim recorded-letter G3 until N-02 (P-26, ADR-149) | P-07 §2.1 |
| — | Work-item sub-lines are plain text until their target screen registers (CLS-02, TAX-02, AUD-02, NOT-02, PRJ-01) | Planned targets are hidden in production | P-07 §2.1 |
| OQ-5 | Segment and tile counts are data-derived; where the seed's tax count differs from "Tax 224" the parity mask covers the count text | DEC-47 backs 214 tax engagements and 224 returns | P-07 OQ-5 decided in DEC-138 |

## Parity
| Artboard | Tier (A/B/C/D) | Diff % | Notes |
|---|---|---|---|
| a, b, c, d | C (locked before M8) | not run (unbuilt) | P0 lock at Tier C (T63); mask segment count text if the seed differs (OQ-5) |
| e | C (report) | not run | mask the skeleton pulse |
| host | D | — | toolbar 46, filter bar 50, tiles 120×72, pane header 46 with a 14.5/500 title, th 30, rows 44, pills 21 |

## Open gaps
- The handoff states no clock for ENG-01; the demo clock E0 is assumed (README note), matching P-07 §5.
- Row 14 belongs to the Walter Thornbury client (DEC-62) and row 16 to its estate entity; TAX-01 and BND-01 label row 14's return "Estate of Walter Thornbury · 2025 Form 1040" because the executor files it. ENG-01 shows the client name the seed gives.
- "Season setup…" appears in P-07 §2.1 but not in spec.md; it is recorded as a planned target and renders nothing until T-08.
