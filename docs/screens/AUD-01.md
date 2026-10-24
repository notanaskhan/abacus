# AUD-01 · Audits index ("All Audits")

| Field | Value |
|---|---|
| Route and params | `/audits` (A-01 §5.1). `?segment=all\|fs\|ebp\|review\|soc\|ia` (default `all`), `?view=list` (`board` reserved for K-04), `?type=`, `?phase=<audit_engagement code>` (a tile toggles it), `?partner=<user id>`, `?office=<office id>`, `?due=any\|7d\|14d\|30d`, `?period=`, `?q=`, `?cursor=`. Filters persist in the URL. Artboards: `/components/screens/AUD-01?st=a…h` |
| Template and host frame | T1 `IndexList` (FilterBar, StatusTileRow, one pane with a ledger DataTable) with the R2 44 px tabs bar (Segmented + ViewToggle) · `Wave 1 - Service Lines.dc.html#aud01` |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/AUD-01 Audits index - All Audits/` (README.md, spec.md, revision.md R2; revision wins, DEC-15) · HANDOFF_VERSION 2026-10-21 |
| Epic and tasks | A-01 · contract A-01-T01 (this file); stub A-01-T02; consumer tests A-01-T03; phase service A-01-T05; scenario slice A-01-T07; read model `GET /v1/audits` A-01-T08; screen a–f live and g, h fixture-only A-01-T11; live swap A-01-T16; Processing swap to C6 v1 A-01-T27; parity and a11y A-01-T28 |
| Manifest status | planned (`routes/manifest/aud.ts`, `navArea: "Audits"`); turns `fixture` with A-01-T11, `live` with A-01-T16 |

Code to come (A-01 §5.2): `src/screens/AUD-01/{index.tsx, scenarios.ts, copy.ts, AUD-01.test.tsx}`, `src/domain/audits/{queries.ts, messages.ts}`, `src/routes/firm/audits.tsx`, `src/fixtures/handlers/audits.ts`. Tags come only from registered index-tag providers (DV-10); the run badge only from C6 v1 engagement runs (DV-11).

## States

25 artboards across AUD-01/02/03; AUD-01 has 9 (a–i). Personas and clocks follow revision.md over the README's "Rendered" column (DV-3): frames a–f are Mon Sep 14, 2026, 9:41 AM CT with 27 audits; g–i are 10:30 AM CT (the wave-7 view, 33 audits and assurance engagements). Persona `hannah-leclerc` exists in the TS seed (`fixtures/seed/shell.ts`).

| Artboard | Viewer (persona) | Clock | Snapshot | Data condition that produces it | Status |
|---|---|---|---|---|---|
| a | hannah-leclerc (Hannah Leclerc, Audit Senior Manager) | Mon Sep 14, 2026, 9:41 AM CT | E0 | 27 assurance work items (blueprint §9.7 A1–A27) by phase, then by report due; no filter | built (T11, live T16) |
| b | hannah-leclerc | 9:41 AM | E0 | `phase=ready_to_release` (tile pressed): 2 rows | built (T11, live T16) |
| c | hannah-leclerc | 9:41 AM | E0 | `due=14d`: rows whose `work_items.due_on` is within 14 days of `kernel.clock` today: 4 rows | built (T11, live T16) |
| d | hannah-leclerc | 9:41 AM | E0 + C6 v1 run summary | Northwind holds an active engagement run (C6 v1): "Processing" replaces its phase pill; the popover opens on hover or focus | fixture (T11); live only once P-10 creates engagement runs (T27, DV-11) |
| e | hannah-leclerc | 9:41 AM | E0 | `q=Pinecrest` matches no row | built (T11, live T16) |
| f | hannah-leclerc | — | E0 | `GET /v1/audits` pending (`never()`) | built (T11) |
| g | hannah-leclerc | Mon Sep 14, 2026, 10:30 AM CT | E2 (wave 7) | 33 rows: A1–A27 plus A28–A33 (group audit, SOC 1/2, internal audit) | fixture only (T11); live when A-09, X-01 and X-03 create those types under their entitlements |
| h | hannah-leclerc | 10:30 AM | E2 | `segment=soc`: Tessellate, Larkfield, Brightline (rows open ATT-01) | fixture only (T11); live with X-01 |
| i | hannah-leclerc | 10:30 AM | E2 | `view=board`: phase columns, C-24 cards that do not drag | deferred → K-04 (C14 board read model; the ViewToggle renders only when C14 registers) |

Non-artboard states (data conditions, never an `st` prop):

| State | Data condition | Rendering |
|---|---|---|
| Error | `GET /v1/audits` answers 5xx | F-05 ViewState error in the pane ("Couldn’t load audits." on the T1 error grammar; see Open gaps) |
| Not allowed | the person lacks `engagement.read_metadata` on every engagement, or is a client principal | 403 by role: the firm route is not reachable from the portal host (INV-4); a firm member with no visible audit gets the empty list ("Showing 0 of 0") |
| Walled | a wall between the viewer and a client (Lena Park and Granite Peak, test wall) | the client's rows are absent from rows, tiles, segments, caption and facets; totals foot without them; a guessed `/audits/<id>` answers 404; no field reveals a hidden count (INV-3, DEC-43) |
| Metadata only | Grace Holloway (firm admin) or `client_service` | rows, phases, PBC counts, EP / Mgr, office and report due; only tags whose provider declares `metadata`; "+ New audit" absent (ADR-024, DEC-20) |
| Flag off | `audits.cockpit` off for the firm | the Audits nav target shows F-05's flag-off ViewState; the legacy board stays reachable until A-01-T21 |
| Entitlement off | the firm holds neither SOC & IT nor Internal audit (Brightwater Hale at E0) | those segments render without a badge and with no rows (revision item 1) |

## API
| Read or write | Endpoint | Shape | Matrix action | allowed_actions and read-only reasons per role |
|---|---|---|---|---|
| read | `GET /v1/audits?segment=&type=&phase=&partner=&office=&due=&period=&q=&cursor=` | `AuditIndexPage` (P-36 envelope): `items[AuditIndexRowOut]`, `next_cursor`, `total`, `counts` per `audit_engagement` code **minus the active tile** (P-36), `facets` (`segment`, `type`, `partner`, `office`, `period`), `summary` (`AuditIndexSummaryOut`: the type caption counts). Row: `work_item_id`, `engagement_id`, `client_name`, `name`, `type_label`, `limited_scope_103a3c`, `period_label`, `phase` (C2 `audit_engagement`), `released_on`, `run_badge` (C6 v1, nullable), `tags[]` (registered providers only), `pbc` (`received`, `total`, nullable before G3), `partner_initials`, `manager_initials`, `office_name`, `report_due_on`, `due_tone`, `archive` (`state` `archiving`\|`archived`\|null, `days_left`, `firm_tool_ref`), `allowed_actions` | `engagement.read_metadata` | every firm role through `visible()`; client roles 403; agent read-only |
| write | — (row click, tile and filters are reads; "+ New audit" navigates to ENG-03) | — | — | "+ New audit" renders only with `engagement.create` in `/v1/me` capabilities |

No response field carries a hidden count, a materiality figure, an amount or a severity (AVOID; INV-3). The contract is `docs/contracts/audits-cockpit.md` (A-01-T02).

## Status
From `docs/product/status-vocabulary.yaml`:
- `audit_engagement`: `planning` "Planning" (state), `fieldwork` "Fieldwork" (state), `in_review` "In review" (state), `ready_to_release` "Ready to release" (green-tint), `released` "Released {date}" (green, solid), `archiving` "Archive in {days} days" (muted + Clock 12), `archived` "Archived" (soon + Lock 12), `processing` "Processing" (state, derived: the run badge, never stored). `completion` "Completion" exists in the registry but has no tile until DF-05 (DV-12).
- `request` counts feed the PBC cell ("11 of 24"): received over total client-visible requests of the work item's published PBC binders; "—" before G3 (DEC-39).
- Report-due tone (`due_tone`, derived from `kernel.clock`): `past_due`/≤ 7 days red-ink 500, ≤ 30 days amber-ink, later ink-2; always with text and a visually hidden "due in n days".

## Copy
Copy keys live in `screens/AUD-01/copy.ts`; every string verbatim from spec.md and revision.md. Names and figures are seed data (A-01-T07).

| Key | String |
|---|---|
| `nav.active` | "Audits" |
| `segments` | "All" · "Financial statement" · "EBP" · "Review & compilation" · "SOC & IT" · "Internal audit" (19h count badges) |
| `viewToggle` | "List" · "Board" (renders only when K-04 registers C14) |
| `filter.type` | "Type │ All" |
| `filter.phase` | "Phase │ All" (b: "Phase │ Ready to release", amber) |
| `filter.partner` | "Partner │ All" |
| `filter.office` | "Office │ All offices" |
| `filter.due` | "Report due │ Any" (c: "Report due │ Next 14 days", amber) |
| `filter.period` | "Period │ PY2025 / FY2026 ⇕" |
| `tiles` | "Planning" · "Fieldwork" · "In review" · "Ready to release" · "Released" (counts 7 · 9 · 6 · 2 · 3 at a) |
| `caption` | "27 engagements · EBP 14 · FS audit 6 · Review 4 · Compilation/preparation 3" (template from `summary`; g: "33 engagements · EBP 14 · FS audit 7 · Review 4 · Compilation/preparation 3 · SOC & IT 3 · Internal audit 2") |
| `search.placeholder` | "Search audits" |
| `showing` | "Showing 27 of 27" (template `Showing {n} of {total}`) |
| `pane.title` | "Audits" |
| `action.new` | "+ New audit" |
| `columns` | "Engagement" · "Type" · "Period" · "Phase" · "PBC" · "EP / Mgr" · "Office" · "Report due" · "Archive" |
| `group` | "PLANNING · 7" · "FIELDWORK · 9" · "IN REVIEW · 6" · "READY TO RELEASE · 2" · "RELEASED · 3" (template `{PHASE} · {n}`, uppercase by CSS) |
| `pbc` | "11 of 24" (template `{received} of {total}`; "—" before G3) |
| `tag.letterSent` | "Letter sent Sep 8" (template `Letter sent {date}`; C1 G3 facts) |
| `tag.eqr` | "EQR · TW" (template `EQR · {initials}`) |
| `tag.noReport` | "No report" |
| `tag.planned` | "Materiality decision pending" · "Rep letter sent" · "Rep letter viewed" · "Component auditor" · "3 exceptions" · "9 issues · 2 overdue" (registered by A-04, A-07, A-09, X-01, X-03; fixture-only until then, DV-10) |
| `pill.released` | "Released Jul 29" (template `Released {date}`) |
| `archive.clock` | "Archive in 13 days" (template `Archive in {days} days`) |
| `archive.done` | "Archived" |
| `archive.tooltip` | "Archived in the firm's tool · CaseWare BH-2025-031" (template `Archived in the firm's tool · {ref}`, DV-4) |
| `run.popover` | "Run 1 · started 9:24 AM by Marcus Delaney · 1 of 14 workpapers complete · blocked on a partner decision" |
| `empty.filtered` | "No results for 'Pinecrest'." (template `No results for '{q}'.`) |
| `empty.clear` | "Clear filters" |
| `board.noDrag` | "Phases follow gates; open the engagement to move work." (i, K-04) |
| `due.hidden` | "due in 4 days" (visually hidden; template `due in {n} days`) |

Per-artboard rows (seed, verbatim from spec.md ROWS and revision.md g): the 27 rows of a with their type labels ("EBP DC · §103(a)(3)(C)", "EBP 403(b)", "FS audit", "Review (AR-C 90)", "Compilation (AR-C 80)", "Preparation (AR-C 70)"), periods ("PY2025", "FYE 6/30/2026", "FYE 3/31/2026", "FYE 12/31/2025", "FY2025"), PBC, EP / Mgr, office and report due exactly as spec.md lists them; g adds Harlow & Pike Holdings, Inc. ("FS audit (group)", "FYE 12/31/2026", tag "Component auditor", PBC "12 drafted" ink-3, MO / OH, Chicago, "Mar 19, 2027"), Larkfield Payroll Services ("SOC 1 Type 2", "Jan 1 – Dec 31, 2026", CM / LK, New York, "Not set"), Prairie Lakes Community Bank ("Internal audit (BSA/AML)", "FY2026", PR / LK, Denver), Tessellate Health Cloud, Inc. ("SOC 2 Type 2", "Oct 1, 2025 – Sep 30, 2026", tag "3 exceptions", "186 of 212", CM / LK, Denver, "Nov 13"), Ashford Manufacturing Co. ("Internal audit (co-sourced)", "FY2026", tag "9 issues · 2 overdue", PR / LK, Chicago) and Brightline Telehealth ("SOC 2 Type 1", "as of Jun 30, 2026", "Released Aug 21", CM / LK, New York, "Archive in 36 days").

## Links
| From | To (manifest builder) | Planned or live |
|---|---|---|
| Row click | AUD-02 `to.AUD02({ auditId })` at Source Documents (`?section=source_documents`) | planned until A-01-T12 (then fixture) |
| PBC cell | AUD-03 `to.AUD03({ auditId })` | planned until A-01-T15 |
| "+ New audit" | ENG-03 with the "Audit & assurance" family preselected | per manifest (P-07) |
| Archive pill | AUD-25 (assembly and archive) | planned (A-07) |
| SOC & IT rows (h) | ATT-01 (tooltip "A29", the handoff's "A30" loses; Deviations) | planned (X-01) |
| Internal audit rows (g, h) | IAU-01 (tooltip "A32", the handoff's "A33" loses; Deviations) | planned (X-03) |
| Harlow & Pike row (g) | AUD-02 frame h (group cockpit) | planned (A-09) |
| EP / Mgr initials | name card popover (O1; local) | in-screen |
| Tiles, filters, segments, search | the same screen with search params | in-screen |

Inbound: SHL-01 (nav "Audits"), SHL-02, HOME-01, AUD-02 and AUD-03 ("All Audits"). Every target is a manifest ID that `link-contract.test.ts` knows; the six designed links of AUD-01 in `handoff-links.json` (ENG-03, AUD-03, AUD-25, AUD-02, ATT-01, IAU-01) are named above. In fixture builds a planned target renders "Not built yet"; in production a control whose target is planned is hidden.

## Acceptance
- AUD-01 acceptance: tiles read Planning 7 · Fieldwork 9 · In review 6 · Ready to release 2 · Released 3 and sum to 27; type counts in the summary line (14/6/4/3) match the Type column.
- AUD-01 acceptance: the chrome matches `audit-evidence.png`: toolbar 46, Audits nav active, hairline table on one white pane with a centered 14.5/500 title.
- AUD-01 acceptance: Northwind shows "Processing" with a spinner instead of a phase pill, PBC "11 of 24", EP/Mgr "MO / HL", report due Oct 9 (d; live only with C6 engagement runs, DV-11).
- AUD-01 acceptance: Bayside's archive clock is consistent: released Jul 29 + 60 days = Sep 27 = "Archive in 13 days" on Sep 14.
- AUD-01 acceptance: Fairhaven shows no PBC count because its engagement letter (G3) is not yet signed.
- AUD-01 acceptance: status words come only from 01 §3.3.1; Released uses the solid green pill, Archived uses soon + lock.
- AUD-01 acceptance: no "$", no materiality and no severity on the index.
- AUD-01 acceptance (R2): frames a–f keep 27 audits; the new segments and toggle appear without changing their rows.
- AUD-01 acceptance (R2): frame g foots: 10 + 11 + 6 + 2 + 4 = 33; segments 7 + 14 + 7 + 3 + 2 = 33.
- AUD-01 acceptance (R2): all six §9.10 rows appear in the right phase with EP CM or PR or MO as seeded; A28 links to the group cockpit (AUD-02 frame h).
- AUD-01 acceptance (R2): the Board shows phase columns and blocks dragging (deferred to K-04 with i).
- A-01 Story 1.2: the selected tile keeps the other tiles' counts (counts minus the active tile); Clear filters resets every filter and the segment.
- A-01 Story 1.4: a walled user's totals foot without the hidden rows and no field carries a hidden count; a client principal gets 403.

## Figures
| Figure | Foots | Proven by |
|---|---|---|
| Tiles (a) | 7 + 9 + 6 + 2 + 3 = 27 | A-01-T03 fixture assertion; A-01-T07 golden |
| Caption (a) | EBP 14 + FS audit 6 + Review 4 + Compilation/preparation 3 = 27 | same |
| Segments (a) | All 27 = Financial statement 6 + EBP 14 + Review & compilation 7 | same |
| Ready to release (b) | 2 of 27 (Cobalt Ridge, Halden Health) | scenario test b |
| Next 14 days (c) | Sep 18, 21, 25, 28 (Fenwick Sep 30 excluded) | scenario test c |
| Archive clock | Jul 29 + 60 = Sep 27 → 13 days on Sep 14; Brightline (g) Aug 21 + 60 = Oct 20 → 36 days | scenario tests a, g |
| Run (d) | 1 of 14 workpapers | scenario test d |
| Wave 7 (g) | 10 + 11 + 6 + 2 + 4 = 33; 7 + 14 + 7 + 3 + 2 = 33 | scenario test g |
| Loading (f) | 5 skeleton tiles, 8 skeleton rows | scenario test f |

## AVOID
Each becomes a test in `AUD-01.test.tsx` ("AUD-01 avoid: …"): gradients in product UI, emoji, saturated blue SaaS accents, heavy shadows, invented colors, lorem ipsum, zebra rows, 600/700 weights, the words Accrual/Arc/ACME/LSA, showing materiality on an index; (R2) dragging an engagement across phases, changing frames a–f, blue, the agent approving anything, "task" for a to-do.

## Deviations
| ID | What differs from the handoff | Why | Decision recorded |
|---|---|---|---|
| DV-3 | Frames a–f at 9:41 AM, g–i at 10:30 AM (the README's 9:24 AM "Rendered" column loses) | revision.md wins (DEC-15) | A-01 §2.4; DEC-260 |
| DV-4 | Phases move in record mode (a named person records Fieldwork and In review) while the matching gate providers are unregistered; "Archived" carries the tooltip "Archived in the firm's tool · ‹reference›" | Phases follow gates, but G4–G5 providers arrive with A-04 and A-06 | A-01 §2.4; DEC-262 |
| DV-5 | Review, compilation and preparation rows open AUD-02 with an SSARS rail (no Planning band) | AUD-26 is A-08 | A-01 §2.4 |
| DV-6 | Report due = `work_items.due_on`; no milestones table | One date per work item suffices in v1 | A-01 §2.4 |
| DV-10 | Tags only from registered providers: "Letter sent ‹date›", "EQR · ‹initials›", "No report" live now; the others fixture-only until their epics register | No source before those epics | A-01 §2.4 |
| DV-11 | "Processing" renders only for C6 engagement runs; v1 policy ticks never show it | Engagement runs start with P-10 | A-01 §2.4 |
| DV-12 | No Completion tile until DF-05's artboard; record mode does not offer Completion before then | Tiles must foot to the total | A-01 §2.4; DF-05 |
| DF-29 | Tooltips read "A29" (Tessellate) and "A32" (Ashford), not the handoff's "A30" and "A33" | Seed row numbers | 09 DF-29 |
| — | i (Board) has no spec letter (README auto-check) and is deferred to K-04 | C14 board read model | A-01 §2.3 |

## Parity
| Artboard | Tier (A/B/C/D) | Diff % | Notes |
|---|---|---|---|
| a–f | C (threshold 0.20, maxDiffPixelRatio 3 %) | not run (unbuilt) | locked by Fri Apr 30, 2027 (A-01-T28); d masks the Processing spinner, f the skeleton pulse |
| g, h | C | not run | report-only (fixture only) |
| i | — | — | deferred to K-04, recorded here, not missing |
| host | D | — | toolbar 46, tabs bar 44, filter bar 50, tiles 120×72 radius 12, pane header 46 with a 14.5/500 title, rows 38, pills 21/19 |

## Open gaps
- No handoff frame exists for the load error; the T1 error grammar is used and its words are fixed in `domain/audits/messages.ts` by A-01-T11.
- The handoff tooltips name rows "A30" and "A33"; DF-29 renumbers them A29 and A32 (decided: DF-29 wins).
- The spec states "≤ 7 days" red-ink and draws Sep 21 (seven days from Sep 14) amber; the rows win: red-ink means fewer than 7 days left, amber 7 to 30 (DEC-263).
- The spec's period chip reads "PY2025 / FY2026" with no other value designed; the period facet lists the periods present after `visible()`.
