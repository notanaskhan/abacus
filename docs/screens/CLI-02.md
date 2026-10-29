# CLI-02 · Client record · Overview

| Field | Value |
|---|---|
| Route and params | `/clients/$clientId` (Overview). Tabs `/clients/$clientId/engagements` · `/relationships` · `/contacts` (CLI-04) · `/activity`; planned and hidden in production: `/tax-profile` (T-01), `/files` (N-01), `/messages` (N-03) (P-07 §5). Artboards: `/components/screens/CLI-02?st=a, a2, b…f` |
| Template and host frame | T2 `RecordCockpit` (rail 330 · canvas 696 · dock 330; F-05-T40) · `Wave 1 - Module Shells.dc.html#cli02` |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/CLI-02 Client record - Overview/` (README.md, spec.md, revision.md R2; revision wins) · HANDOFF_VERSION 2026-10-21 |
| Epic and tasks | P-07 · contract P-07-T01 · fixtures P-07-T11 · screen P-07-T19 · read models P-07-T09 (record, overview), P-07-T10 (TIN reveal) · Activity tab P-07-T57/T61 · parity lock P-07-T63 |
| Manifest status | planned (`routes/manifest/cli.ts`, path `/clients/$clientId`, `navArea: "Clients"`); built on fixtures behind `clients.v2` by P-07-T19 (TASK-988) and kept `planned` until `to.<ID>()` can ship without the manifest names (DEC-195) |

Code to come (P-07 §5): `src/screens/CLI-02/{index.tsx, scenarios.ts, copy.ts, CLI-02.test.tsx}`, `src/domain/clients/{queries.ts, mutations.ts, MaskedTin.tsx}` (F-05-T14's Reveal primitive inside `MaskedTin`). Flag `clients.v2`.

## States

7 artboards post-revision (a, a2, b, c, d, e from spec.md; f from revision.md R2). P-07-T19 built 6 (a, a2, b, c, e, f; scenarios in `fixtures/scenarios/CLI-02.ts`, tests in `screens/CLI-02/CLI-02.test.tsx`, axe in `e2e/screens/CLI-02.spec.ts`); d waits on P-09-T09 (Deviations).

| Artboard | Viewer (persona) | Clock | Snapshot | Data condition that produces it | Status |
|---|---|---|---|---|---|
| a | daniel-reyes (Daniel Reyes, Tax Partner) | Mon Sep 14, 2026, 9:24 AM CT | E0 | Ridgeline Property Partners, LP (business kind): 2 active engagements, 11 open issues on the 2025 return, 5 waiting on client, K-1s 2 of 5 shared as drafts, extended due Sep 15 | built · live (T19); K-1 "Feeds" links fixture until T-05; the dock thread is the d fixture's |
| a2 | daniel-reyes | same | E0 | a with the rail scrolled: the Client Portal and Links bands | built · live (T19) |
| b | daniel-reyes | same | E0 | Jonah & Claire Feld (household kind): SSN masked, filing status MFJ, one 1040 holding a draft Ridgeline K-1 | built · live (T19); the §7216 consent summary row and the CCH sync chip are fixture until T-01 |
| c | daniel-reyes | same | E0 | Northwind Robotics, Inc. (plan sponsor, attest client by DEC-128): PBC 11 of 24, run "Processing", SKE designee Dana Kowalski, independence 4 of 5 confirmed | built · live (T19) |
| d | daniel-reyes | same | E0 | The agent dock is answering ("Searching K-1 packages and relationships…"): a scripted run fixture | not built: no API carries the dock thread until P-09-T09 (SHL-13 dock host) on P-10 runtime v2 |
| e | daniel-reyes | same | E0 | Copperleaf Coffee Roasters, Inc. on its onboarding day: no engagements | built · live (T19) |
| f | margaret-okonkwo (Margaret Okonkwo) | Thu Oct 1, 2026, 10:30 AM CT | E0 + Oct 1 snapshot | Granite Peak Outdoor Supply, Inc. with entitlement `insights` on: the Client responsiveness card | built · fixture until I-03 (INS-05 read model, entitlement `insights`) |

Loading: skeleton stat values and band rows (F-05 ViewState). Not-allowed: a walled or unknown client answers 404 and renders not-found (INV-3). Firm admin (Grace Holloway, metadata-only, ADR-024): the subbar, Details, team and counts render; sections whose read action needs content (waiting-on-client detail, K-1 feeds) are omitted, not disabled. Error: the ViewState error frame. Flag off: the flag-off ViewState.

## API
| Read or write | Endpoint | Shape | Matrix action | allowed_actions and read-only reasons per role |
|---|---|---|---|---|
| read | `GET /v1/clients/{client_id}` | Subbar facts, tab counts, `allowed_actions`, `version` | `client.read` | every firm role (metadata); walls answer 404 |
| read | `GET /v1/clients/{client_id}/overview` | Per-kind profile (business, household, plan sponsor, empty) from registered section providers, each filtered by its own read action | `client.read` + each section's own read action | content sections omitted for metadata-only roles |
| read | `GET /v1/clients/{client_id}/relationships` | Relationship list (edges into walled clients omitted) | `client.read` | as above |
| read | `GET /v1/engagements?client_id=` | Engagements tab and "2 active engagements ⌄" menu | `engagement.read_metadata` | visible engagements only |
| write | `PATCH /v1/clients/{client_id}` | `relationship_partner_id` (Team band Partner picker), `descriptor`, `primary_office_id`, `status`; `seen_version` | `client.update` | firm_admin, partner, manager; others read-only (picker absent) |
| write | `POST /v1/client-entities/{entity_id}/tin/reveal` | `{reason}` → plaintext once, `Cache-Control: no-store`; one `tin.revealed` audit event with the reason code, never the value | `tin.reveal` | engagement_partner, manager, eqr_reviewer; senior and staff only with `function_in(preparer, first_level_reviewer)`; `not_offshore`; `mfa_recent`; the control is absent when not allowed |

## Status
`engagement` (Active, Accepted, …) for the "2 active engagements ⌄" menu; work-item words from their own objects: return "In review · Partner", "In review · Manager"; project "Scoping"; `return_sync_chip` "Not yet exported", "Synced {date}"; K-1 `draft` "Draft K-1 · pre-release"; agent run "Processing". Client status and portal words ("Active") arrive with P-07-T03 (DF-31). Risk pill "Moderate risk" (amber) is the acceptance record's risk rating.

## Copy
Copy keys live in `screens/CLI-02/copy.ts`; strings verbatim from spec.md and revision.md.

| Key | String |
|---|---|
| `subbar.back` | "‹ All Clients" |
| `tabs` | "Overview" · "Engagements" · "Relationships" · "Contacts & access" · "Tax profile" · "Files" · "Messages" · "Activity" (counts are data: Engagements 2, Contacts & access 5, Messages 1) |
| `rail.title` | "Summary" |
| `rail.engagementsPill` | "{n} active engagements ⌄" (a: "2 active engagements ⌄") |
| `rail.bands` | "Details" · "Team" · "Client Portal" · "Links" |
| `details.keys` | "EIN" · "Fiscal year end" · "Accounting method" · "Attest client" · "Office" (b: "SSNs" · "Filing status" · "Resident" · "§7216 consents"; c: "Plan" · "SKE designee" · "Independence") |
| `tin.reveal` | "Reveal (logged)" |
| `team.keys` | "Partner" · "Manager" · "Preparer" |
| `portal.keys` | "Contact" · "Email" · "Status" · "Portal" · "Requests" |
| `portal.identities` | "{n} identities" |
| `portal.pending` | "{n} pending" |
| `links.keys` | "Entities" · "Relationships" · "Files" · "Binder" · "Messages" |
| `links.files` | "{client}'s Files →" |
| `canvas.title` | "Overview" |
| `canvas.message` | "Message…" |
| `canvas.newEngagement` | "+ New engagement" |
| `card.activeWork` | "Active work" |
| `card.k1` | "K-1 packages · TY2025" with columns "Recipient" · "Box 2" · "Status" · "Feeds"; total row "Total = Schedule K" |
| `card.waiting` | "Waiting on client · {n}" |
| `card.waiting.all` | "View all {n} in Issues" |
| `card.keyDates` | "Key dates" |
| `card.recent` | "Recent activity" |
| `card.responsiveness` (f) | "Client responsiveness"; cells "ON-TIME RATE" · "FIRM" · "OVERDUE NOW" |
| `responsiveness.footer` (f) | "Season to date Jan 1 – Sep 30, 2026 · on time = completed by its due date · compared with the firm rate" |
| `responsiveness.flag` (f) | "Below the firm rate — noted for the FY2027 continuance." (the handoff's trailing "(CLI-07)" becomes the line's link; see Deviations) |
| `responsiveness.links` (f) | "Open in Insights" · "Draft follow-ups…" |
| `dock.title` | "Agent" |
| `dock.composer` | "Ask about this client" |
| `dock.running` (d) | "Searching K-1 packages and relationships…" |
| `empty.title` (e) | "No engagements yet." |
| `empty.action` (e) | "+ New engagement" |

Stat rows, KV values, card rows, key dates, recent-activity lines and the dock's question and answer are seed data (spec.md a, b, c; revision f), never `copy.ts`. The dock answer renders through `AgentText` only.

## Links
| From | To (manifest builder) | Planned or live |
|---|---|---|
| "‹ All Clients" ("Opens CLI-01 · all clients") | CLI-01 `to.CLI01()` | planned (P-07-T12) |
| Engagements tab; Active-work rows of an engagement | ENG-01 filtered to this client · ENG-02 `to.ENG02({ engagementId })` | planned (P-07-T27, P-07-T20) |
| "+ New engagement" (canvas, e) ("Opens ENG-03, prefilled with this client") | ENG-03 | planned (P-07-T21) |
| Contacts & access tab; Portal "5 identities →" | CLI-04 | planned (P-07-T33) |
| Tax profile tab | CLI-05 | planned (T-01); tab hidden in production |
| Files tab; Links "Files" ("Opens FIL-01 · client folder") | FIL-01 | planned (N-01); hidden in production |
| Messages tab; "Message…"; Links "Messages" ("Opens INB-04 · new message to this client") | INB-04 | planned (N-03); hidden in production |
| Links "Binder" ("Opens BND-02 · 2025 Binder") | BND-02 | planned (P-06-T12) |
| Active-work return row; K-1 "Feeds" links ("Opens TAX-02 · return overview") | TAX-02 | planned (T-02); Feeds rows fixture until T-05 |
| Active-work advisory row ("Opens PRJ-01 · advisory project") | PRJ-01 | planned (T-09) |
| Active-work audit row (c) ("Opens AUD-02 · audit cockpit") | AUD-02 | planned (A-01) |
| Active-work close row | CLS-02 | planned (C-01) |
| Stat rows "Open issues", "Waiting on client"; "View all 5 in Issues" ("Opens TXP-10 · issues") | TXP-10 | planned (T-05) |
| Stat row "K-1s shared as drafts" ("Opens TXP-12 · K-1 packages") | TXP-12 | planned (T-02) |
| Stat row "To extended due date" ("Opens HOME-03 · deadlines") | HOME-03 | planned (T-08) |
| Details "Independence · 4 of 5 confirmed" (c) ("Opens CLI-08 · independence and conflicts") | CLI-08 | planned (P-07-T48) |
| f: 48% and "Open in Insights" ("Opens INS-05 · Client responsiveness · Granite Peak selected") | INS-05 | planned (I-03); fixture only |
| f: "Draft follow-ups…" ("Opens BND-04 · 3 overdue requests") | BND-04 | planned (N-03); fixture only; a person sends |
| f: the flag line ("Opens CLI-07 · FY2027 continuance (frame g)") | CLI-07 | planned (P-07-T46); fixture only |
| Relationships tab, Links "Relationships" | the in-record relationship list (`/clients/$clientId/relationships`) | in-screen (list until T-06) |
| "Reveal (logged)" | a reason dialog (Dialog 400, local state) | in-screen |

The handoff's Relationships tooltip "Opens CLI-03 · relationships" names a screen the screen index does not list (`handoff-links.json` `unindexed`, DEC-32); the graph lands with T-06 and gets a manifest entry then. Inbound: CLI-01, every "Client ›" link (AUD-02 rail, ENG-02 rail, TXP and EBP screens, TAX-02, CLS-02), SHL-02. All targets in the table are manifest IDs that `link-contract.test.ts` knows.

## Acceptance
- CLI-02 acceptance: the rail copies close-overview: "Summary" header, centered name block with a "⌄" pill (no icon tile), 15/400-over-12 stat rows with chevrons, "Details" and "Client Portal" bands with KV rows (Status Active, Requests "5 pending" = the five waiting-on-client issues).
- CLI-02 acceptance: link values are ink with an ink-3 "→".
- CLI-02 acceptance: K-1 box 2 rows sum to 1,231,600 (= Schedule K); Feld 307,900 and Shah 468,008 show "Draft K-1 · pre-release" with their internal hand-offs; the other three also read "Draft K-1 · pre-release" with no internal handoff; all five release together Sep 15, 2026, 10:30 AM.
- CLI-02 acceptance: Ridgeline status words are §3.3.1: "In review · Partner" and the sync chip "Not yet exported"; the project reads "Scoping".
- CLI-02 acceptance: the EIN is masked XX-XXX0287; Reveal is logged.
- CLI-02 acceptance: the dock answers with citations and names only Ridgeline-related records (fixture until P-09).
- CLI-02 acceptance: three columns at 330 · 696 · 330 with 10-px gaps; all titles centered except the canvas title (left).
- CLI-02 acceptance (R2): frames a–e are unchanged.
- CLI-02 acceptance (R2): frame f shows 48% against the firm's 63% and 3 overdue requests, with the season-to-date footnote.
- CLI-02 acceptance (R2): links reach INS-05 and BND-04; follow-ups are sent by a person.
- CLI-02 acceptance (R2): no other client's figures appear on the record.
- P-07 §3.1 Story 1.3: Reveal asks for a reason, shows the value for 10 seconds, announces it through a polite live region, re-masks and returns focus to the button; one `tin.revealed` event; offshore members and roles without `tin.reveal` never get the button.

## Figures
| Figure | Foots | Proven by |
|---|---|---|
| K-1 box 2 (a) | 24,632 + 468,008 + 400,270 + 30,790 + 307,900 = 1,231,600 = Schedule K | P-07-T11 seed footing test |
| K-1s shared (a) | "2 of 5" = Feld + Shah hand-offs of 5 packages | same |
| Requests (a) | "5 pending" = "5" waiting on client = TXP-10's five waiting-on-client issues | same |
| Contacts (a) | Contacts & access 5 = Portal "5 identities" | same |
| Due (a) | "1 day" from Mon Sep 14 to Sep 15 | clock test |
| Feld (b) | "31 days" to Oct 15; Requests open 2 (CLI-01 Feld 2) | same |
| Northwind (c) | PBC "11 of 24" (CLI-01 open 13 = 24 − 11); "4 of 5 confirmed" (CLI-08 a) | same |
| Granite Peak (f) | 48% vs 63%; 3 overdue (FY2026 audit requests) | P-07-T11 fixture test (I-03 owns the read model) |

## AVOID
Gradients in product UI, emoji, saturated blue, heavy shadows, invented colors, lorem ipsum, unmasked TINs, CRM-style avatars or social links, colored record headers, data from any other client in the agent's answer. R2: other clients' rates or rankings on this record; donut or gauge charts; numerals above 15px in the card; changing frames a–e; blue; the agent sending follow-ups; "task" for a to-do.

## Deviations
| ID | What differs from the handoff | Why | Decision recorded |
|---|---|---|---|
| OQ-7 | Team band: Partner is the stored relationship partner with a picker; Manager and Preparer are derived from engagement teams and read-only (no ⌄), linking to ENG-05 | The client team is derived, not stored | DEC-62; P-07 OQ-7 decided in DEC-138 |
| — | Production renders T2 without the dock slot until P-09 registers the SHL-13 dock host; a, b, c, e keep the dock thread only in fixture builds (parity runs there) | No agent runtime on this surface in v1 (P-07 §6) | P-07 §2.1, §2.3 |
| — | "Reveal (logged)" opens a reason dialog (Dialog 400 from kits) before showing the value | Reveal is logged with a reason code (P-12, DEC-52); the reason dialog is undesigned (P-07 R-9) | P-07 §3.1 Story 1.3 |
| — | Tax profile, Files and Messages tabs, "Message…", and the Links rows "Files" and "Messages" are hidden in production until T-01, N-01 and N-03 | Planned targets are hidden in production (chapter 04 §2.1 rule 4) | P-07 §2.1 |
| — | The Activity tab is hidden until P-07-T61 wires it to G-02's audit_trail read API; the Overview "Recent activity" card renders the same projection | Cut order item 4 | P-07 §2.3 |
| — | P-07-T61 (DEC-822): Activity is a live tab in production (the track has room). In fixture builds, where the planned tabs fill the seven, the route's `/activity` opens it. Amended copy: "No activity yet" (empty), "Activity didn't load" (error); lines are ADM-07's words (`titleOf`, `detailOf`) | C-05's seven a track | DEC-822 |
| — | f's flag line drops the parenthesised "(CLI-07)": screen IDs inside handoff strings are canvas cross-references, and the line itself links to CLI-07 | Internal codes never show in product chrome | DEC-138 |
| — | No dock in any build, and d is not built | The dock thread has no API until P-09-T09; screens read data only through the generated client | DEC-195 |
| — | The tab track holds seven options: Activity is dropped rather than hidden-but-drawn | C-05's seven-option limit; Activity is hidden until P-07-T61 anyway | DEC-195 |
| — | The Engagements tab lists the record's active engagements in the canvas (each opens ENG-02) instead of opening ENG-01 filtered | ENG-01 is planned (P-07-T27) | DEC-195 |
| — | Links into and out of CLI-02 are wired in `routes/firm/clients.tsx`, and the manifest entry stays `planned` | `to.<ID>()` carries the manifest names the production dist must not hold | DEC-195 |
| G-1…G-9 | See Contract gaps | The contract's generic section item | DEC-195 |

### Reveal dialog (P-07-T19; undesigned, P-07 R-9)
| Key | String |
|---|---|
| `tin.title` | "Reveal taxpayer ID" |
| `tin.description` | "The reveal is logged with your reason." |
| `tin.reason` | "Reason" — options "Prepare the return" · "Review the return" · "File or correct a filing" · "Respond to a notice" · "Verify identity" (DEC-141's codes) |
| `tin.confirm` | "Reveal" |
| `tin.revealed` (live region) | "Taxpayer ID shown for {n} seconds." |
| `tin.remasked` (live region) | "Taxpayer ID masked again." |
| `partner.saved` · `partner.stale` | "Partner updated" · "This client changed since you opened it. Reload to see the latest." |

### Contract gaps (P-07-T19)
The overview is a list of generic sections (`ClientOverviewItemOut`: `key`, `text`, `figure`, `on`, `at`, `pill_object`, `pill_code`, `ref`). The screen draws what an item carries and invents nothing (DEC-195):
| Gap | What the handoff draws | What the screen draws until the provider carries it | Owner |
|---|---|---|---|
| G-1 | Active-work sub-lines ("Extended due Sep 15 · OB / SI · DR signs · Form 7004 filed Mar 12, 2026") | title, pill, open-issue count | T-02, T-09 |
| G-2 | the review level in "In review · Partner" | "In review" (`return.in_review`) | T-02 |
| G-3 | the white sync chip "Not yet exported ⌄" / "Synced Sep 10 ⌄" on a work item | nothing | T-01 (TAX-09) |
| G-4 | K-1 "Feeds" labels ("Shah 1040 →", "Feld 1040 →") | an arrow with the TAX-02 hint when the item has a `ref` | T-05 |
| G-5 | the waiting-on-client requester ("Owen Calder · sent Sep 11") | the sent date | T-05 |
| G-6 | the §7216 consent pill ("Signed · expires Dec 31 2026") | the consent text | T-01 |
| G-7 | the "x of y" stats ("2 of 5", "11 of 24") | two items, `<key>` and `<key>.of` | P-07 (an additive `denominator` on the item) |
| G-8 | "Accounting method: Accrual · income-tax basis books" (a) | the row is absent: the value is T-01's, and its first word is the one the brand lint bans in source | T-01 |
| G-9 | the dock thread (a–e) and d | not built | P-09-T09 |

## Parity
| Artboard | Tier (A/B/C/D) | Diff % | Notes |
|---|---|---|---|
| a, b, c, e | C (locked before M8) | not run (P-07-T63) | P0 lock at Tier C (T63); built without the dock |
| a2 | C (report) | not run | rail scrolled |
| d | C (report) | not run | fixture only; mask the spinner |
| f | C (report) | not run | fixture only (I-03); canvas crop 696 wide |
| host | D | — | toolbar 46, subbar 42, tabsbar 50, pane header 46, columns 330 · 696 · 330, KV rows 33, stat rows 15/400 over 12 |

## Open gaps
- spec.md says Reveal shows "00-0000287"; the revealed value is the seed's synthetic EIN, never written into `copy.ts`. P-07 §3.1 states the masked shape as `•••-••-1234`; for an EIN the handoff mask "XX-XXX0287" wins in the UI, and the API carries `{masked, revealable}` either way.
- c names Northwind Robotics, Inc. a plan sponsor and attest client; the attest flag is the derived `is_attest_client` (DEC-128), never edited on this screen ("Attest client: No" on a is the same flag).
- The R2 revision says frames a–e "predate" the Insights card; in production the card renders only with entitlement `insights` (I-03), so a–e stay as designed.
