# TPL-01 · Index list specimen · Tax Returns (TY2025 practice board)

| Field | Value |
|---|---|
| Route and params | Gallery only: `/components/specimens/tpl-01?st=a…e&as=hannah-leclerc&clock=2026-09-14T09:24:00-05:00`. Production twin TAX-01 `/tax-returns` (T-02) |
| Template and host frame | T1 (F-05 `IndexList` + `FilterBar` + `StatusTileRow`) · `Wave 0 - Templates.dc.html#tpl01` |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/TPL-01 Index list specimen - Tax Returns/` (README.md, spec.md; no revision.md) · HANDOFF_VERSION 2026-10-21 sha256:9308819d |
| Epic and tasks | F-06 · F-06-T01 contract; F-06-T02 seed; F-06-T08 specimen a–e; F-06-T13 lock |
| Manifest status | planned (twin TAX-01, T-02) |

Code: specimen `apps/web/src/gallery/specimens/TPL-01/` over `apps/web/src/fixtures/seed/tax/tax-returns.ts` and `envelopes.ts`. Copy keys: `apps/web/src/gallery/specimens/TPL-01/copy.ts`.

## States
| Artboard | Viewer (persona) | Clock | Snapshot | Data condition that produces it | Status |
|---|---|---|---|---|---|
| a · Default | `hannah-leclerc` | E0 Mon Sep 14, 2026, 9:24 AM CT | E0 | TY2025 list: 224 returns, 79 open, 145 done, 161 extended; `counts` facet; first page of 15 sorted by extended due date then client | built in F-06-T08 |
| b · Filtered by tile | `hannah-leclerc` | E0 | E0 | `search: {tile: "awaiting_signature"}`: 10 of 10, exactly the returns behind E1–E10; Signature column with `SignerChips` | built in F-06-T08 |
| c · Filtered empty | `hannah-leclerc` | E0 | E0 | `search: {q: "Schwab"}`: no match; tiles and count hidden | built in F-06-T08 |
| d · Loading | `hannah-leclerc` | E0 | E0 | `override: {"GET /tax-returns": never()}`: real header and columns, skeleton tiles and 8 rows after 200 ms | built in F-06-T08 |
| e · Season start | `hannah-leclerc` | E0 | E0 | `search: {tax_year: 2026}`: no TY2026 returns; tiles all 0 | built in F-06-T08 |
| error | `hannah-leclerc` | E0 | — | the list request fails: `ViewState error` with Try again | built in F-06-T08 |
| not allowed | a viewer without `tax_return.read` | E0 | — | the T1 not-allowed state | built in F-06-T08 |

## API
| Read or write | Endpoint | Shape | Matrix action | allowed_actions and read-only reasons per role |
|---|---|---|---|---|
| read | `GET /tax-returns` (T-02; not built) | list envelope with `items`, `counts` facet (excludes the tile filter), `total` | `tax_return.read` (T-02) | Bulk actions items render only when `allowed_actions` carries them (Manager and up) |
| write | none | Bulk actions, + New return and row clicks are callbacks | — | — |

## Status
`return` object (§3.3.1): `prepared`, `in_review` ("In review · {level}"), `action_required` (tile label "Issues", the `home_and_tax_tiles` context label), `approved`, `gathering`, `preparing`, `awaiting_signature`, `filed`, `accepted`; `return_flag.extended` ("Ext." micro tag); `return_sync_chip` ("Not yet exported", "Ready for export", "Synced {date}"). Tile "Ready" is `approved`; tile "Filed · Accepted" counts `filed` plus `accepted`.

## Copy
`TPL-01/copy.ts`: filter chips ("Form", "Office", "Partner", "Preparer", "Due", "Tax year") · summary "79 open · 145 done · 224 TY2025 returns · 161 extended" · "Showing {shown} of {total} open" · "Search returns" · "Tax Returns" · "Bulk actions" · "+ New return" · columns (Return, Client, Office, Prep / Rev, Status, Issues, Engine sync, Due, Days, Signature) · "Ext." · "{n} day(s)" · bulk items "Assign preparer…", "Extend…", "Run firm standards…" · "No results for '{q}'." · "Clear filters" · "No TY2026 returns yet." · "Roll clients forward from TY2025 to create returns, binders and assignments." · "Open season setup".

Tile order (recorded here as T01's decision, DEC-801): Prepared 17 · In review 15 · Issues 11 · Ready 7 · Gathering 8 · Preparing 9 · Awaiting signature 10 · Filed · Accepted 145. Not started (2) is open and has no tile.

## Links
| From | To (manifest builder) | Planned or live |
|---|---|---|
| Row | TAX-02 return overview (T-02) | planned |
| Issues count | TAX-06 (T-02) | planned |
| Sync chip | TAX-09 popover (T-02) | planned |
| + New return | ENG-03 wizard | live (ENG-03) |
| Signature chips | SIG-01 (N-02) via `onOpenSignatures(envelopeId)` | planned |

## Acceptance
- TPL-01 acceptance: tiles read Prepared 17 · In review 15 · Issues 11 · Ready 7 first, in neutral, state, red-tint and green-tint, and the summary totals 79 open / 145 done / 224.
- TPL-01 acceptance: split "Label │ Value ⇕" filter chips; only an active chip is amber.
- TPL-01 acceptance: one white pane with 10 px gutters and a 46 header with a centred 14.5/500 title.
- TPL-01 acceptance: status words come only from the registry.
- TPL-01 acceptance: days-to-due colour ≤ 7 days red-ink, ≤ 30 amber-ink, later ink-2, from the demo clock.
- TPL-01 acceptance: eight tiles in TAX-01's order; 8 + 9 + 17 + 15 + 11 + 7 + 10 + 2 = 79.
- TPL-01 acceptance: every sync chip is a white e1 chip with an olive check disc when synced.
- TPL-01 acceptance: the Awaiting signature filter shows exactly the ten returns behind E1–E10.

## Figures
8 + 9 + 17 + 15 + 11 + 7 + 10 + 2 = 79; 79 + 145 = 224; Awaiting signature = E1–E10 (10). Proven by `tax.foot.test.ts` (F-06-T02).

## AVOID
Gradients, emoji, saturated blue, heavy shadows, invented colours, lorem ipsum, zebra rows, 600/700, "$" amounts, the words Accrual/Arc/ACME.

## Deviations
| ID | What differs from the handoff | Why | Decision recorded |
|---|---|---|---|
| a | Column header "Due" | the glossary bans "deadline" as an identifier | F-06 Story 2.3 |
| a | Row 4 status reads "Action required" in the table and "Issues" on the tile | `home_and_tax_tiles` context label | DF-31, DECISIONS.md |
| a | Tile counts are the server's `counts` facet; rows are never counted in the browser | INV-3 (walled rows such as Ashford for Lena Park never reach the kit) | F-06 Story 2.1 |

## Parity
| Artboard | Tier (A/B/D) | Diff % | Notes |
|---|---|---|---|
| a–e | B frame · A strips · D geometry | not run | not locked: the specimen board is 1440 wide against the 1400 window crop (F-06-T13 end review); report-only until the specimen draws the 1400 window |

## Open gaps
- No `revision.md`. The spec text puts "Ready" before Gathering in the first group; TAX-01's order is recorded above.

## Hand-off (F-06-T13, 2026-10-30)
- **T-02 (TAX-01, the TY2025 practice board):** the specimen's frames are locked at Tier B against the handoff PNGs (`docs/design/parity-manifest.json`, pinned SHA-256); the consumer screen composes the same template, so the template's own geometry and chrome are fixed. Masks per F-06 §5.4 (provider frame, KBA timer, spinners).
