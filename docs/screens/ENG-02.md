# ENG-02 · Engagement record

| Field | Value |
|---|---|
| Route and params | `/engagements/$engagementId` (Overview). Tabs `/work-items` · `/team` (ENG-05) · `/letter` (record card until ENG-04) · `/activity`; `/roll-forward` (ENG-13, O6); planned and hidden in production: `/dashboard` (ENG-12) · `/board` (ENG-10) · `/budget` (ENG-06) · `/settings` (ENG-11, the gear) (P-07 §5). Artboards: `/components/screens/ENG-02?st=a…g` |
| Template and host frame | T2 `RecordCockpit` without dock (summary rail 330 + canvas 1036; F-05-T40) · `Wave 1 - Module Shells.dc.html#eng02` |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/ENG-02 Engagement record/` (README.md, spec.md, revision.md R2; revision wins) · HANDOFF_VERSION 2026-10-21 |
| Epic and tasks | P-07 · contract P-07-T01 · fixtures P-07-T11 · record projection and interim G3 P-07-T15 · screen core P-07-T20 (b, c, d, e, prospect banner, Record signed letter sheet) · remaining P-07-T28 (a, Work items, Team host, On hold, f, g) · Activity P-07-T57/T61 · parity lock P-07-T63 |
| Manifest status | planned (`routes/manifest/eng.ts`, path `/engagements/$engagementId`, `navArea: "Engagements"`); core built on fixtures behind `engagements.v2` by P-07-T20 (TASK-988), kept `planned` for CLI-02's reason (DEC-195) |

Code to come (P-07 §5): `src/screens/ENG-02/{index.tsx, scenarios.ts, copy.ts, ENG-02.test.tsx}`, `src/domain/engagements/{queries.ts, mutations.ts, GateBlock.tsx}`. Flag `engagements.v2`.

## States

7 artboards post-revision (a–e from spec.md; f, g from revision.md R2) plus one spec'd non-artboard state; all 8 built here: 5 live, 1 live with fixture-only blocks, 2 fixture-only.

| Artboard | Viewer (persona) | Clock | Snapshot | Data condition that produces it | Status |
|---|---|---|---|---|---|
| a | priya-raman (Priya Raman, CAS & Advisory Partner) | Mon Sep 14, 2026, 9:24 AM CT | E0 | Copperleaf Coffee Roasters, Inc. "2026 Close", Active, CAS (non-attest), letter signed Mar 3, 2026; August close 4 days past due | built (T28, TASK-1127): rail, the 12 close rows with "7 of 12", the SKE note; the stat rows, RunCard, Year-end and Related groups wait for C-01's close provider (DEC-272) |
| b | priya-raman | same | E0 | Northwind Robotics 401(k) Plan "PY2025 EBP Audit", Active: gate rows G1–G3 met (live providers), G4 blocked; G5–G9 rows render only for registered providers | built · live (T20) |
| c | priya-raman | same | E0 | Bluestem Analytics, LLC "2026 Close (from Oct)", Accepted, letter viewed Sep 11 and not signed: G3 unmet, no work items | built · live (T20) |
| d | priya-raman | same | E0 | Meridian Tool & Die, Inc. "FY2025 FS Audit", Archived, archive locked Jun 12, 2026 (WORM): every write answers 409 `archived` | built · live (T20) |
| e | priya-raman | same | E0 | `GET /v1/engagements/{id}` never answers (`never()` handler) | built · live (T20) |
| prospect (no artboard) | priya-raman | same | E0 | The Estate of Walter Thornbury engagement, Prospect: acceptance pending with Daniel Reyes; Work items holds the intake's Form 706, Form 1041 and Form 1040 (DEC-430; J19 3, P-07-T62) | built · live (T20) |
| f | margaret-okonkwo (Margaret Okonkwo) | Tue Oct 6, 2026, 11:20 AM CT | Oct 6 snapshot | Granite Peak Outdoor Supply, Inc. "FY2026 Financial Statement Audit" on the Dashboard tab (the ENG-12 default) | built (T28) · fixture: the tab hosts ENG-12's planned target until K-04 (DEC-272) |
| g | priya-raman | Mon Sep 14, 2026, 9:24 AM CT | E0 | Copperleaf on the Board tab (the ENG-10 close variant) | built (T28) · fixture: the tab hosts ENG-10's planned target until K-04 (DEC-272) |

Not-allowed: a walled or unknown engagement answers 404 and renders not-found (INV-3). A metadata-only role (firm admin) sees the rail and gates; content bands need `engagement.read`. Error: the ViewState error frame. Flag off: the flag-off ViewState.

## API
| Read or write | Endpoint | Shape | Matrix action | allowed_actions and read-only reasons per role |
|---|---|---|---|---|
| read | `GET /v1/engagements/{engagement_id}` | Extended F-03 projection: subbar facts, rail bands (Details, Review and Delivery, Client Portal), contacts block (approver of record, SKE designee), letter summary, `gates`, tab counts, `read_only_reason` (`archived`), `allowed_actions` | `engagement.read_metadata`; content bands need `engagement.read` | team roles, practice leader `in_scope`, firm admin (metadata) |
| read | `GET /v1/engagements/{engagement_id}/gates` | `[{gate, met, blockers: [ObjectRef]}]` for registered providers (G1, G2, interim G3 in P-07; G4–G9 when A-04, A-06, A-07 register) | `engagement.read_metadata` | as above |
| write | `PUT /v1/engagements/{engagement_id}/letter` | Record signed letter (O3 sheet): client and firm signature dates, signers, signed copy (write-once evidence); G1 met and date after the acceptance decision, else 409 `letter_before_acceptance`; EP exception when `allow_letter_exceptions` | `letter.record` + `gates_met(G1)` | engagement partner, manager; agent and system deny |
| write | `POST /v1/engagements/{engagement_id}/hold` `{reason}` · `POST …/resume` (TASK-1198, DEC-328) over F-03's lifecycle move (`engagements/transitions.py`: active ⇄ on_hold, events `engagement.held` / `engagement.resumed`) | Status menu: Active ⇄ On hold… (reason code required) | `engagement.hold` | engagement partner, manager, `mfa_recent`; disabled on archived (409 `archived`) |
| write | Team pickers (Review and Delivery band) | the existing team routes (`GET/POST/PUT/DELETE …/team`) | `engagement.member_add/remove` | partner, manager; the picker shows independence chips; G2 blocks the assignment of a pending member on an attest engagement |

## Status
`engagement`: Prospect · Accepted · Letter signed · Active · On hold · Delivered · Archived (`status-vocabulary.yaml`); the status pill ⌄ offers Active and "On hold…". `close` rows: Delivered · Locked · In progress · Not started. `return` "Delivered · Accepted"; `notice` "Analyzing"; agent run "Processing". Gates read met (olive ✓), blocked (amber triangle), not started (ring).

## Copy
Copy keys live in `screens/ENG-02/copy.ts`; strings verbatim from spec.md and revision.md.

| Key | String |
|---|---|
| `subbar.back` | "‹ All Engagements" |
| `subbar.contracted` | "Contracted {date}" (a: "Contracted Mar 3, 2026") |
| `subbar.openClose` (a) | "Open August close ›" |
| `tabs` | "Overview" · "Dashboard" · "Board" · "Work items" · "Team" · "Letter & terms" · "Budget" · "Activity" (counts are data: Work items 12, Team 3) |
| `gear.tooltip` | "Engagement settings" |
| `rail.title` | "Summary" |
| `rail.bands` | "Details" · "Review and Delivery" · "Client Portal" |
| `details.keys` | "Client" · "Entity" · "Service" · "Period" · "Office" · "Close plan" · "Letter" · "Fee" (b: "Client" · "Entity" · "Type" · "Standards" · "Methodology" · "Office" · "Letter" · "Fee") |
| `review.keys` | "Due date" · "Partner (reviewer)" · "Preparer" · "Client service" |
| `portal.keys` | "Contact" · "Approver of record" · "Portal" · "Connections" · "Reminder" |
| `portal.skeNotRequired` | "SKE designation not required — {client} is not an attest client." (a: "SKE designation not required — Copperleaf is not an attest client.") |
| `canvas.title` | "Overview" |
| `canvas.activity` | "Activity ›" |
| `run.title` (a) | "August 2026 close is running" |
| `run.sub` (a) | "3 tasks running at once." |
| `run.progress` (a) | "6 of 9 complete" · "Started 18 minutes ago" |
| `group.monthly` | "Monthly closes"; sub "Jan–Dec 2026 · due the 10th of the following month"; "View plan" · "New close ⌄" |
| `group.yearEnd` | "Year-end work"; sub "Opens after the December close" |
| `group.related` | "Related engagements"; sub "Same client" |
| `row.actions` | "Open" · "View work" |
| `group.gates` (b) | "Gates" |
| `group.workItems` (b) | "Work items" |
| `banner.g3` (c) | "Work items open when the letter is signed (G3). Letter viewed by {person} · {date}." (c: "… Letter viewed by Arjun Mehta · Sep 11.") |
| `banner.g3.action` (c) | "Open letter" |
| `empty.workItems` (c) | "No work items yet." |
| `archived.lock` (d) | "Archive locked {date} · WORM" (d: "Archive locked Jun 12, 2026 · WORM") |
| `archived.postLock` (d) | "Post-lock additions: 0" |
| `banner.prospect` | "Acceptance pending — {partner} · Open acceptance ›" ("Acceptance pending — Daniel Reyes · Open acceptance ›") |
| `status.menu` | "Active" · "On hold…" |
| `status.dialog` (undesigned, DEC-344) | title and action "Put on hold"; "Choose why the engagement is on hold. Set it back to Active from the status menu."; fieldset "Reason" |
| `status.reasons` (DEC-344) | "Client unresponsive" · "Fees outstanding" · "Scope change" · "Independence review" · "Other" (the API's five codes, DEC-328) |
| `status.toasts` (DEC-344) | "Engagement on hold" · "Engagement active"; refused: "Only an active engagement can go on hold." · "Couldn’t change the status." |

Rail values, task rows, gate facts ("Continuance approved by MO · May 28", "Letter signed by Dana Kowalski and MO · Jun 2", "Materiality blocked on a partner decision"…), related rows and f's dashboard tiles and milestones are seed data, never `copy.ts`. The Record signed letter sheet (O3) is composed from kits; its strings are recorded in this contract by P-07-T20 before it merges (P-07 §2.1, R-9).

## Links
| From | To (manifest builder) | Planned or live |
|---|---|---|
| "‹ All Engagements" ("Opens ENG-01 · all engagements") | ENG-01 `to.ENG01()` | planned (P-07-T27) |
| Details "Client ›" ("Opens CLI-02 · client record") | CLI-02 `to.CLI02({ clientId })` | planned (P-07-T19) |
| Details "Letter ›" and the Letter & terms tab ("Opens ENG-04 · engagement letter") | ENG-04 | planned (N-02); until then the tab hosts the record-mode card and "Record signed letter…" |
| A sent letter ("Opens SIG-01, filtered to this envelope") | SIG-01 | planned (N-02) |
| Team tab | ENG-05 | planned (P-07-T39) |
| Budget tab (sub-seg Billing) | ENG-06 · ENG-08 | planned (I-04); hidden in production |
| Dashboard tab (f) | ENG-12 | planned (K-04); fixture only |
| Board tab (g) ("Opens ENG-10 · the board inside this record (see ENG-02g).") | ENG-10 | planned (K-04); fixture only |
| The gear ("Engagement settings") | ENG-11 | planned (K-04); hidden in production; ink-4 and disabled on d |
| Roll forward | ENG-13 | planned (P-07-T60) |
| Prospect banner "Open acceptance ›" | CLI-07 | planned (P-07-T46) |
| Task row "Open"; "Open August close ›" ("Opens CLS-02 · August 2026 close") | CLS-02 | planned (C-01); fixture until then |
| "View work" ("Opens CLS-06 · close review") | CLS-06 | planned (C-01); fixture only |
| "View plan"; Details "Close plan ›" ("Opens CLS-09 · close plan editor") | CLS-09 | planned (C-01); fixture only |
| Year-end rows ("Opens CLS-13 · 1099 / W-9 tracker", "Opens CLS-12 · handoff to tax") | CLS-13 · CLS-12 | planned (C-02); fixture only |
| Related row TY2025 Form 1120-S ("Opens TAX-02 · TY2025 Form 1120-S") | TAX-02 | planned (T-02) |
| Related row notice ("Opens NOT-02 · notice workspace") | NOT-02 | planned (N-04) |
| b Work items row ("Opens AUD-02 · audit cockpit") | AUD-02 | planned (A-01) |
| b G4 row ("Opens AUD-07 · materiality decision (SHL-11)") | AUD-07 | planned (A-04) |
| Stat row "Past due" ("Opens HOME-03 · deadlines") | HOME-03 | planned (T-08) |
| Client Portal "Portal ›" ("Opens CLI-04 · contacts and portal access") | CLI-04 | planned (P-07-T33) |
| Client Portal "Reminder: Draft Email ›" ("Opens SHL-14 · reminder composer") | SHL-14 | planned (P-06) |
| Inside the ENG-12 dashboard on f (kit tooltips) | INS-05 · AUD-03 · AUD-15 · SHL-17 · SHL-20 · ENG-06 · ENG-11 · WB-11 | planned (I-03, A-01, A-06, P-05, P-06, I-04, K-04, W-01); fixture only, specified by ENG-12's contract |
| Inside the ENG-10 board on g (kit tooltips) | CLS-04 · ATT-05 | planned (C-01, X-01); fixture only, specified by ENG-10's contract |
| Status pill ⌄; Person ⌄ pickers; "Record signed letter…" | a menu, a staff picker with independence chips, the O3 record-letter sheet (local) | in-screen |

Inbound: ENG-01, ENG-03 ("Create"), ENG-04, ENG-08, ENG-11, CLI-02 Engagements tab, SHL-02, CLS-02 rail "Engagement ›", AUD-21, AUD-22, AUD-29, HOME-05, PRJ-01, SIG-01, TAX-02, TPL-10, TXP-00. All targets are manifest IDs that `link-contract.test.ts` knows.

## Acceptance
- ENG-02 acceptance: side by side with close-overview, the same 42px title line, a 50px tab row with a centered segmented control, a 330 Summary rail, and a flex canvas whose run card and task groups have identical paddings and type sizes.
- ENG-02 acceptance: the stat rows reuse the close grammar: big value 15/400 over a 12px ink-3 label, with a chevron.
- ENG-02 acceptance: Copperleaf numbers tie to blueprint §9.4: 43% (9/21), 7 open issues, 58 documents, Run 2 at 6 of 9 with 3 running, started 18 minutes ago, due Sep 10 so 4 days past due.
- ENG-02 acceptance: "7 of 12" closes delivered equals the count of ✓ rows (January–July).
- ENG-02 acceptance: Approver of record is Ben Ashby, with the explicit "SKE designation not required" note (non-attest client).
- ENG-02 acceptance: in the audit variant the gates read G1–G3 ✓ and G4 blocked, matching the AUD-02 materiality block.
- ENG-02 acceptance: no status word outside §3.3.1; close rows use Delivered, Locked, In progress and Not started.
- ENG-02 acceptance (R2): tabs read Overview · Dashboard · Board · Work items 12 · Team 3 · Letter & terms · Budget · Activity, plus the gear (fixture build; production shows only the live tabs).
- ENG-02 acceptance (R2): the gear opens ENG-11; it is disabled on the archived record.
- ENG-02 acceptance (R2): frame f matches ENG-12's Oct 6 tiles and milestones exactly (report release Oct 27, due Oct 28).
- ENG-02 acceptance (R2): frames a–e keep their rail, run card and task groups.
- P-07 §3.6 Story 6.2: the G3 banner clears only after a recorded letter signed by both parties and dated after the acceptance decision; d disables every action and the gear and the server answers 409 `archived` to any write.

## Figures
| Figure | Foots | Proven by |
|---|---|---|
| Closes (a) | "7 of 12" = 7 ✓ rows (January–July) | P-07-T11 seed footing test |
| August close (a) | 43% = 9 / 21 reconciled; 7 open issues; 58 documents; 4 days past due (due Sep 10, clock Sep 14) | same; blueprint §9.4 |
| Run (a) | 6 of 9 complete = 66.7% bar; 3 running; started 18 minutes ago | fixture test (C-01 owns the run) |
| Year-end (a) | "0 of 2" | same |
| Gates (b) | G1–G3 met, G4 blocked, G5–G9 not started | P-07-T15 gate provider test |
| Work items (b) | PBC "11 of 24 received" (CLI-02 c, CLI-01 13 = 24 − 11) | P-07-T11 |
| Dashboard (f) | Programs complete 12 of 21 · Ready for review 2 · Overdue requests 3 · Sign-offs 62%; milestones Planning approved Sep 14 · Fieldwork Sep 21 – Oct 16 · Statements draft Oct 21 · Report release Oct 27 (due Oct 28) | fixture test against ENG-12 (K-04) |

## AVOID
Gradients in product UI, emoji, saturated blue, heavy shadows, invented colors, lorem ipsum, a left sidebar nav, progress bars per row, colored row backgrounds, showing billing internals to the client, the words Accrual/Arc/ACME. R2: a new top-nav item; settings in a modal; restating ENG-10 or ENG-12 differently; changing rail or canvas content in frames a–e; blue; the agent approving anything; "task" for a to-do. From P-07 §5: internal engagement numbers in chrome.

## Deviations
| ID | What differs from the handoff | Why | Decision recorded |
|---|---|---|---|
| DF-22 | Production shows Overview · Work items · Team · Letter & terms · Activity; Dashboard, Board, Budget and the gear are hidden until K-04 and I-04 register them | Planned targets are hidden in production | DF-22; P-07 §2.1 |
| — | Letter & terms hosts a record-mode card with "Record signed letter…" (O3 sheet) instead of the ENG-04 composer; the Letter link opens it | Interim recorded-letter G3 until N-02 (P-26, ADR-149) | P-07 §2.1, DEC-64 |
| — | The prospect pre-acceptance banner is built without a frame, from spec.md's ENG-01 interaction text | Spec'd, undesigned state | P-07 §2.1 |
| — | a's RunCard and close task groups render only in fixture builds until C-01 registers the close kind provider; production shows the engagement's work-item rows | C-01 owns closes | P-07 §2.1 |
| — | The Activity tab is hidden until P-07-T61; "Activity ›" in the canvas header is its placeholder | Cut order item 4; R2's eight tabs exceed C-05's seven a track | P-07 §2.3, DEC-272 |
| — | P-07-T61 (DEC-822): Activity is a live tab in production (the track has room). In fixture builds, where the planned tabs fill the seven, "Activity ›" in the canvas header opens it. Amended copy: "No activity yet" (empty), "Activity didn't load" (error); lines are ADM-07's words (`titleOf`, `detailOf`) | C-05's seven a track | DEC-822 |
| DEC-272 | Dashboard, Board and Budget tabs host their planned targets' "Opens …" line (fixture builds only); the gear is drawn disabled (ENG-11 planned) and marked on d | ENG-12, ENG-10, ENG-06 and ENG-11 are K-04's and I-04's to build ("do not restate") | DEC-272 |
| DEC-272 | The Team tab hosts the roster from `GET …/team` (name, role words) until ENG-05 | P-07-T39 builds ENG-05 | DEC-272 |
| DEC-344 | The status pill ⌄ (Active · "On hold…") opens a sm Dialog with the five reason codes as a radio group; while on hold the reason word reads beside the pill (`hold_reason` on the record). Offered only with `engagement.hold` in `allowed_actions` on an Active or On hold record | spec.md says only "On hold asks for a reason"; the dialog is undesigned | DEC-344, DEC-328 |
| DEC-272 | a draws no stat rows, RunCard, Year-end or Related groups; closes read their phase word, not spec.md's meta lines | Not in the record or `WorkItemOut`; C-01's close provider | DEC-272 |
| — | The core's tabs are in-screen state (Overview, Work items, Letter & terms; Team drawn disabled in fixture builds), not the `/work-items`, `/team`, `/letter` routes | P-07-T28 adds the tab routes with the Team host | DEC-195 |
| — | ENG-02 → CLI-02 is wired in `routes/firm/engagements.tsx`, and the manifest entry stays `planned` | As CLI-02 | DEC-195 |
| G-1…G-4 | See Contract gaps | The v2 record projection | DEC-195 |

### Record signed letter sheet (O3 500; P-07-T20; undesigned, P-07 R-9)
Opened by "Record signed letter…" on the Letter & terms card, enabled when the record allows `letter.record`, G1 is met, the letter is not signed and the record is not archived.
| Key | String |
|---|---|
| `letter.title` | "Letter & terms" (card) · rows "Status" (the `letter_record` word) and "Signed" (the date) |
| `letter.record` | "Record signed letter…" |
| `letter.sheetTitle` | "Record signed letter" |
| `letter.sheetDescription` | "Record the letter both parties signed. The dates must fall after the acceptance decision." |
| rows | "Client signed on" · "Client signer" · "Firm signed on" · "Firm signer"; date placeholder "YYYY-MM-DD"; select placeholder "Choose" |
| `letter.save` | "Record letter" (disabled until both dates are YYYY-MM-DD) |
| `letter.saved` (toast) | "Letter recorded" |
| errors | `letter_before_acceptance` "The signature dates must fall after the acceptance decision." · `gate_unmet` "The acceptance decision (G1) is not recorded yet." · `engagement_archived` "This engagement is archived." · a malformed date "Enter a date as YYYY-MM-DD." · otherwise "Couldn’t record the letter." |

The signed copy (`signed_copy_version_id`) is not uploaded from the sheet yet: the evidence upload intent for a firm-side document is not on this surface (gap G-3 below).

### Contract gaps (P-07-T20)
| Gap | What the handoff draws | What the screen draws | Owner |
|---|---|---|---|
| G-1 | gate facts as sentences ("Continuance approved by MO · May 28", "5 of 5 confirmed · Kira Ross pending assignment", "Materiality blocked on a partner decision") | the gate payload in registry words: "MO · May 28", G3 "Letter signed by Dana Kowalski and MO · Jun 2", "Blocked on a partner decision", "Not started" | P-07-T15 (an additive facts line per provider) |
| G-2 | who viewed the letter in the G3 banner | the record's `signing_officer` designation | P-07-T15 (`viewed_by` on the letter summary) |
| G-3 | the signed copy on the recorded letter | dates and signers only | P-07-T15, N-02 |
| G-4 | the work-item row's sub-line ("Processing · PBC 11 of 24 received") | the name and the phase pill | P-07-T15, A-01 |

## Parity
| Artboard | Tier (A/B/C/D) | Diff % | Notes |
|---|---|---|---|
| b, c, d | C (locked before M8) | not run (unbuilt) | P0 lock at Tier C (T63) |
| a, e | C (report) | not run | a on the fixture build (RunCard); mask the spinner and skeleton pulse |
| f, g | C (report) | not run | fixture only (K-04) |
| host | D | — | toolbar 46, subbar 42, tabsbar 50, pane header 46, rail 330 + canvas 1036, KV rows 33, task rows per close-overview |

## Open gaps
- Viewer for b: spec.md says Margaret Okonkwo; the README screenshot table and revision.md ("Viewer: Priya Raman (a–e, g)") say Priya Raman. The revision wins: priya-raman, as P-07 §2.1 records.
- b's G2 fact reads "5 of 5 confirmed · Kira Ross pending assignment", while CLI-08 a at the same clock reads "4 of 5 confirmed" with Ana Cruz pending. The gate row renders the G2 provider's facts, never copy; the fixture keeps the handoff text for parity, and P-07-T11 makes the seed state one answer and notes which artboard its parity mask covers.
- README describes b as "blocked at G4" for Margaret Okonkwo and the AUD-02 materiality block; G4 is registered by A-04, so until then the b row renders only from fixture data and production shows G1–G3.
- The spec's "Letter & terms" and "Letter ›" route to ENG-04; until N-02 both open the record-mode card, whose layout P-07-T20 adds to this contract.
