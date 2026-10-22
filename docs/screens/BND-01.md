# BND-01 · Binders index

| Field | Value |
|---|---|
| Route and params | `/binders` (P-06 §5.1). Search params `service`, `season`, `office`, `preparer`, `activity`, `status`, `q`, `cursor`; a tile toggles `status`. Artboards: `/components/screens/BND-01?st=a…e` |
| Template and host frame | T1 `IndexList` (FilterBar, StatusTileRow, ledger DataTable) · `Wave 1 - Module Shells.dc.html#bnd01` |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/BND-01 Binders index/` (README.md, spec.md; no revision) · HANDOFF_VERSION 2026-10-21 |
| Epic and tasks | P-06 · contract P-06-T03 (TASK-404); a, c, d, e P-06-T09; b and the follow-up sheet P-06-T16; read model P-06-T11; data P-06-T08; parity P-06-T26 |
| Manifest status | planned (`routes/manifest/bnd.ts`, `navArea: "Binders"`) |

Code to come (P-06 §5.2): `src/routes/firm/binders.tsx`, `src/domain/requests/` (`queries.ts`, `mutations.ts`, `filters.ts`, `messages.ts`, `FollowUpSheet.tsx`), `src/screens/BND-01/{index.tsx, scenarios.ts, copy.ts, BND-01.test.tsx}`.

## States

5 artboards in the handoff, 5 built here.

| Artboard | Viewer (persona) | Clock | Snapshot | Data condition that produces it | Status |
|---|---|---|---|---|---|
| a | grace-holloway (Grace Holloway, Firm Admin) | Mon Sep 14, 2026, 9:24 AM CT | E0 | Service │ Tax returns, Season │ TY2025; the 241 TY2025 tax-return binders, first 15 rows by newest client activity within each state | built · fixture (T09) |
| b | grace-holloway | same | E0 | Client activity │ None in 30 days (published binders only): one row, Fenwick Family Foundation (last activity Aug 11); the row is selected, so the bulk bar shows | built · fixture (T16, with the follow-up sheet) |
| c | remy-vidal (Remy Vidal) | same | E0 | Benjamin Osterberg's binder is `unpublished` with `unpublish_reason` "fixing 2 requests", Sep 2 by Remy Vidal | built · fixture (T09) |
| d | grace-holloway | same | E0 | Season │ TY2026: no binders in the season | built · fixture (T09) |
| e | grace-holloway | same | E0 | `GET /v1/binders` never answers (`never()` handler) | built · fixture (T09) |

Not-allowed: a walled binder is absent from rows, tiles and totals and a guessed `/binders/<id>` answers 404; nothing says a row is hidden (INV-3, DEC-43). Error: F-05's ViewState error frame. Flag off (`binders.engine`): F-05's flag-off ViewState at `/binders`.

## API
| Read or write | Endpoint | Shape | Matrix action | allowed_actions and read-only reasons per role |
|---|---|---|---|---|
| read | `GET /v1/binders?service=&season=&office=&preparer=&client_activity=&status=&q=&cursor=` | P-36 list envelope `{items, next_cursor, total, counts, facets}`; `counts.status` feeds the tiles, computed after `visible()` | `binder.read` | every firm engagement role and `client_service` (metadata only, DEC-20); tax-return binders add `not_offshore` (fails closed until C19) |
| write | `POST /v1/binders` | Create Draft `{work_item_id, kind, name?, from_binder_id?, template_ref?}` ("+ New binder") | `binder.create` | partner, manager; senior and `client_service` by firm setting; agent deny |
| write | `POST /v1/binders/{id}/publish` · `/unpublish {reason}` · `/duplicate` | Row ··· menu | `binder.publish` · `binder.create` | unpublish requires a reason (422 `reason_required`); publish answers 409 `binder_gate_unmet` before G3 except `intake` |
| write | `POST /v1/follow-ups/drafts {binder_ids[]}` · `POST /v1/follow-ups/send {ids[]}` | One follow-up draft per client contact, items never repeated; bulk human send | `follow_up.draft` · `follow_up.send` | agent deny on send (DEC-74) |

## Status
`binder` (`status-vocabulary.yaml`): `draft` Draft (neutral) · `published` Published (state) · `unpublished` Unpublished (muted) · `complete` Complete (green-tint, "Marked done by {person}") · `closed` Closed (soon). The locked end state is an Archive (FIL-01), never a binder status. Count bad (#F7E4E1/#8E2418) "3 overdue" is derived from `request.overdue`.

## Copy
Copy keys live in `screens/BND-01/copy.ts`; every string below is verbatim from spec.md.

| Key | String |
|---|---|
| `filters.service` | "Service │ Tax returns" |
| `filters.season` | "Season │ TY2025" |
| `filters.office` | "Office │ All offices" |
| `filters.preparer` | "Preparer │ All" |
| `filters.activity` | "Client activity │ Any" |
| `filters.activityNone` | "Client activity │ None in 30 days" |
| `filters.clear` | "Clear" |
| `tiles` | "Draft" · "Published" · "Unpublished" · "Complete" · "Closed" |
| `summary` | "241 TY2025 binders · 224 returns · 17 second-part binders" |
| `pane.title` | "Binders" |
| `pane.search` | "Search binders" |
| `pane.showing` | "Showing 15 of 241" |
| `pane.sendReminders` | "Send reminders…" |
| `pane.newBinder` | "+ New binder" |
| `columns` | "Binder" · "Client" · "Work item" · "Requests" · "Status" · "Last client activity" · "Prep" |
| `requests.progress` | "{done} of {total}" (for example "5 of 7") |
| `status.complete` | "Marked done by {person} · {date}" |
| `status.unpublished` | "Unpublished Sep 2 by Remy Vidal — fixing 2 requests" (template "Unpublished {date} by {person} — {reason}") |
| `status.draftSub` | "Not published · return Not started" |
| `status.k1Draft` | "K-1 from Ridgeline · Draft K-1 · pre-release" |
| `status.overdue` | "3 overdue" (template "{n} overdue") |
| `status.consents` | "§7216 consents 1 of 2" |
| `bulk.selected` | "1 selected · Send reminder… (Request Chaser draft)" |
| `empty.title` | "No TY2026 binders yet." |
| `empty.body` | "Season setup creates binders from each client's TY2025 return." |
| `empty.action` | "Open season setup" |
| `menu` | "Publish" · "Unpublish" · "Duplicate as pt 2" · "Open in Files" |

Row text (binder names, clients, work items, status sub-lines, last-activity lines) is data from the Brightwater Hale binder slice (P-06-T08), copied from spec.md ROWS 1–15, never from `copy.ts`. "Send reminder(s)…" stays the UI word; identifiers say `follow_up` (DV-7).

## Links
| From | To (manifest builder) | Planned or live |
|---|---|---|
| A row | BND-02 `to.BND02({ binderId })` ("Opens BND-02 · 2025 Binder · Jonah & Claire Feld (click to select)") | planned (P-06-T12 builds BND-02) |
| Last client activity cell, when the activity was an email | INB-04 ("Opens the Inbox thread (INB-04)") | planned (N-03) |
| "Open season setup" (d) | ENG-07 ("Opens ENG-07 · season setup and roll-forward") | planned (T-08, S50) |
| Ferris tag "§7216 consents 1 of 2" | CLI-05 ("Opens CLI-05 · consents") | planned (P-07) |
| ··· "Open in Files" | FIL-01 | planned (spec-level only; not in `handoff-links.json`) |
| "Send reminders…", bulk "Send reminder…" | the follow-up sheet (O3, local state) | in-screen |
| "+ New binder" | a sheet (client, work item, template; local state) | in-screen |

Inbound: SHL-01 nav "Binders", SHL-02, TAX-03 "Binder ›", TAX-07, TAX-09. All targets are manifest IDs that `link-contract.test.ts` knows.

## Acceptance
- BND-01 acceptance: tiles foot to 241 (1 + 48 + 0 + 40 + 152), matching §9.5 "binders 241".
- BND-01 acceptance: statuses come only from §3.3.1 Binder (Draft · Published · Unpublished · Complete · Closed); "Complete" carries "Marked done by {client}".
- BND-01 acceptance: binders for Gathering returns (Thornbury, Mendez, Ferris, Lakeshore, Fenwick) are Published; Quintero's (return Not started) is still a Draft; accepted returns (Whitley, Copperleaf) are Closed.
- BND-01 acceptance: the Feld row (5 of 7, Published, 2 open) matches BND-02, TAX-03 and TPL-07 (Intake 2); Meera Shah shows the Ridgeline K-1 as an internal draft.
- BND-01 acceptance: last-activity dates agree with HOME-01's feed (Calloway Sep 9; Thornbury Sep 9) and the Inbox (Feld 9:12 AM, Mendez yesterday).
- BND-01 acceptance: T1 grammar as TPL-01: 50px filter bar, 120×72 tiles, a single pane with a centered title.
- P-06 §3.2: a walled user sees no walled binder in rows, tiles or totals, and no response field reveals a hidden count.
- P-06 §3.2: "Send reminder…" drafts one follow-up per client contact; nothing is sent until a person clicks Send.

## Figures
| Figure | Foots | Proven by |
|---|---|---|
| Tiles | 1 + 48 + 0 + 40 + 152 = 241 | P-06-T08 footing test; P-06-T29 golden figures |
| Summary | 224 returns + 17 second-part binders = 241 | same |
| Feld | 5 of 7 | same, and BND-02 a |
| Fenwick (b) | last activity Aug 11 → 34 days before Sep 14 (over 30) | same |
| Showing | 15 rows of 241 | scenario test |
| Loading (e) | 8 skeleton rows | scenario test |

## AVOID
Gradients in product UI, emoji, saturated blue, heavy shadows, invented colors, lorem ipsum, red for client-missing items in the client's own words, zebra rows, the words Accrual/Arc/ACME.

## Deviations
| ID | What differs from the handoff | Why | Decision recorded |
|---|---|---|---|
| DV-7 | UI keeps "Send reminder(s)…"; code identifiers say `follow_up` (L12 applies to identifiers only) | DEC-74 vocabulary; the handoff copy is final | P-06 §2.4 |
| — | Bulk send drafts come from the firm's Reminder template (C16), never model text; the agent never sends | DEC-74, DEC-79 off, ADR-111 | P-06 §3.2 Story 2.2 |
| — | No "Binders · Requests" segmented control until N-03 builds BND-04 | BND-04 is N-03's | P-06 §2.1 |

## Parity
| Artboard | Tier (A/B/C/D) | Diff % | Notes |
|---|---|---|---|
| a–e | C (threshold 0.20, maxDiffPixelRatio 3 %) | not run (unbuilt) | locked (blocking) at the end of S10; mask the skeleton pulse in e |
| host | D | — | toolbar 46, subbar 42, pane header 46 with a 14.5/500 title, rows 38/44, pills 21/19/18, radius 12 |

## Open gaps
- Last client activity is the `binder_activity` projection (portal upload, answer, sign and `inbox_file.added` events); the inbound-email part may move to N-01 under cut order item 3 (P-06 §11.3).
- The Ferris "§7216 consents 1 of 2" tag needs P-07/T-01 to register the consent-tag hook; until then the tag renders only in fixture mode.
- Personas `grace-holloway` and `remy-vidal` are added to the scenario by P-06-T08 if F-04 has not.
