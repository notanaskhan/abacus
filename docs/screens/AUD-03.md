# AUD-03 · Source documents / PBC with viewer

| Field | Value |
|---|---|
| Route and params | `/audits/$auditId/source-documents` (A-01 §5.1). `?item=<requestItemId>` (selected row; loads the viewer), `?sort=missing_first\|received_first` (default `missing_first`), `?q=`. Overlays: `?ov=request:new\|<id>` (SHL-14, P-06), `?ov=export` (A-01-T24); the ReturnDialog, FollowUpSheet and ScreeningCard are local state (P-06). Legacy redirect `/engagements/$id/requests` → here (A-01-T16). Artboards: `/components/screens/AUD-03?st=a…g` |
| Template and host frame | T2 with the audit split: rail 330 · canvas 536 · viewer 490 (dock = Viewer; F-05 SplitLayout audit preset) · `Wave 2 - Audit Planning.dc.html#aud03` |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/AUD-03 Source documents - PBC with viewer/` (README.md, spec.md, revision.md R2; revision wins, DEC-15) · HANDOFF_VERSION 2026-10-21 |
| Epic and tasks | A-01 · contract A-01-T01 (this file); stub A-01-T02; consumer tests A-01-T03 (C5 v1.1 additive fields); cockpit L3 A-01-T06; C5 v1.1 fields and Source Documents aggregate A-01-T10 (N); screen A-01-T15; remind and third-party wiring, live swap and redirect A-01-T16; legacy retirement A-01-T21; parity A-01-T28 |
| Manifest status | planned with path `/audits/$auditId/source-documents` (`routes/manifest/aud.ts`): A-01-T15 built a–g on fixtures and A-01-T16 wired the live P-06 routes, but it stays `planned` for AUD-02's reason (DEC-195: "+ Add" is SHL-14, an overlay with no `to.<ID>()` builder). DEC-421, DEC-422 |

Code (A-01 §5.2): `src/screens/AUD-03/{index.tsx, scenarios.ts, copy.ts, AUD-03.test.tsx}`; fixtures `src/fixtures/{seed/aud03,scenarios/AUD-03}.ts`; the viewer's lit match, slot and logged reveal in `domain/audits/{DockViewer,reveal}.tsx`; delegation in `domain/requests/delegate.ts`. Originally planned: on `domain/audits` (rail, audit bar) and `domain/requests` (ReturnDialog, FollowUpSheet, ScreeningCardHost from P-06-T22), `src/domain/evidence/` (logic moved from the legacy screens, A-01-T21). A-01-T21 retired the legacy Board, ItemDetail and AIReviewPanel without a `domain/evidence` folder: nothing of their logic is used by AUD-03, and the legacy paths `/engagements/$id/requests` and `/engagements/$id/items/$itemId` only redirect here (`?item=`). SPEC-330 §8 maps every superseded assertion (DEC-442).

## States

AUD-03 has 7 artboards (a–g). Viewer **Ana Cruz** (`ana-cruz`, Staff) for every frame (DV-3); state c is the Sep 9 snapshot as built, f the late-September snapshot, g the Sep 21 snapshot.

| Artboard | Viewer (persona) | Clock | Snapshot | Data condition that produces it | Status |
|---|---|---|---|---|---|
| a | ana-cruz (Ana Cruz, Staff) | Mon Sep 14, 2026, 9:41 AM CT | E0 | Northwind's 24 requests, Missing first on; BrokerWindow asset detail selected; its page shows Gordon Whitfield's holdings | built (T15, live T16) |
| b | ana-cruz | 9:41 AM | E0 | The certified trust report selected: `uploaded` with a fulfilment at match 94% and a passed screening (Sep 11); `staff_can_accept_evidence` on (DEC-37) | built (T15, live T16) |
| c | ana-cruz | Wed Sep 9, 2026 | Sep 9 | The matcher's 62% proposal (BrokerWindow detail ← Schedule of Account Balances) held; flagged screening | fixture (T15); live from the scenario's Sep 9 snapshot |
| d | ana-cruz | 9:41 AM | Sep 9 | "Return…" pressed on c: P-06's ReturnDialog (O3) with Wrong document preselected | built (T15) |
| e | ana-cruz | 9:41 AM | E0 | The IRS opinion letter selected (`requested`, owed by Dana Kowalski) | built (T15, live T16) |
| f | ana-cruz | late September | all received | every Northwind request `received` | fixture (T15) |
| g | ana-cruz | Mon Sep 21, 2026 | Sep 21 | rows due Sep 18 still `requested`: `overdue` derived from `due_on < clock.today()` | fixture (T15) |

Non-artboard states:

| State | Data condition | Rendering |
|---|---|---|
| Loading | `GET /v1/audits/{id}/source-documents` pending | skeleton rows in the canvas; viewer well empty |
| Error | the read fails | F-05 error ViewState in the canvas |
| Not found | walled, other tenant, not assurance | 404 (INV-3) |
| Staff accept off | `staff_can_accept_evidence` off | `allowed_actions` omits `accept` for staff; the strip shows only "Return…" with the read-only reason |
| Agent / system / support | any decision attempt | accept and send-back 403; the database refuses an agent decision row (INV-1) |
| Withdrawn upload | a client withdrew an unaccepted upload (P-31) | the row returns to its prior status; the file is absent from the viewer and the export |
| Offshore member | `not_offshore` fails | "Reveal (logged)" never renders |

## API
| Read or write | Endpoint | Shape | Matrix action | allowed_actions and read-only reasons per role |
|---|---|---|---|---|
| read | `GET /v1/audits/{work_item_id}/source-documents?binder=&q=&sort=` | `SourceDocumentsOut` (A-01-T02 stub; T10 live): `received` 11, `total` 24, `needs_review` 1, `requested` 12, `groups[]` (`category`, `label`, `received`, `total`, `collapsed`, `note`, `rows[]`) with the C5 v1.1 row fields below; "Sample-driven · 0" band not counted | `request_item.read` | as P-06 |
| read | `GET /v1/binders/{id}/requests` (P-06, **C5 v1.1 additive**) | + `owed_by {kind, display}`, `requested_on`, `latest_upload {path_label, uploaded_on, uploader_kind}`, `match_confidence`, `linked_count`, `screening_verdict` (`passed`\|`flagged`\|`not_screened`), `overdue` (derived) | `request_item.read` | — |
| read | P-03 viewer: pages, regions, `pii-reveals` | C4 | as owned | "Reveal (logged)" with fresh MFA; `pii.revealed` audited without the value |
| write | `POST /v1/engagements/{eid}/evidence-versions/{vid}/decision/accept` | `review_decisions` accept, actor kind human | `evidence.accept` | staff with `firm_setting(staff_can_accept_evidence)` (DEC-37), senior and above; never an agent |
| write | `POST …/evidence-versions/{vid}/decision/send-back` `{reason, message?}` | send_back with reason `wrong_document` etc. | `evidence.reject` | same roles; reason required |
| write | `POST /v1/follow-ups/drafts {request_item_ids}` (P-06) | one draft per contact; a person sends after the 10-s Undo | `follow_up.draft` / `follow_up.send` | — |
| write | P-06 delegate endpoint | delegation to Sam Ortiz with a `request_item` grant | as owned | — |
| write | `POST …/request-items/{id}/uploads` | Replace (a new version on behalf) | `evidence.upload` | — |

## Status
- `request`: `received` "Received" + 15 px olive disc (demo grammar), `requested` 15 px empty ring, `uploaded` "Uploaded – needs review" (amber 19h), `returned` "Returned · wrong document" (red-tint), `overdue` "Overdue" (red-tint, derived, never stored).
- `evidence_screening` glyph (12 px, tooltip "Evidence screening · Passed|Flagged|Not screened"): olive ✓ Passed, amber triangle Flagged, ring Not screened. The card never shows a percentage (DEC-48); "Match 94%" in the strip is the matcher's fulfilment confidence.
- The rail repeats AUD-02's `audit_engagement` and `audit_section` words.

## Copy
Copy keys live in `screens/AUD-03/copy.ts`. Verbatim from spec.md and revision.md.

| Key | String |
|---|---|
| `canvas.add` | "+ Add" |
| `canvas.title` | "Source Documents" |
| `canvas.remind` | "Remind…" |
| `canvas.search` | "Search" |
| `canvas.missingFirst` | "Missing first" |
| `groups` | "Plan documents" · "Trust / Recordkeeper Reports" · "Census & Payroll" · "Form 5500 & SOC 1" · "Cash" · "Compliance & other" with "3 of 5" · "4 of 6" · "3 of 7" · "1 of 4" · "0 of 1" · "0 of 1" (template `{received} of {total}`) |
| `group.sampleDriven` | "Sample-driven · 0" · "Item requests are generated after Sample Selection." |
| `row.requested` | "Requested Sep 1 · due Sep 18 · Dana Kowalski" (template `Requested {date} · due {date} · {owed_by}`; owed-by "Sam Ortiz, Keystone", "Harborline Trust Company", "PayGrid Payroll", "Summit Plan Administrators") |
| `row.received` | "initial-input/Northwind SPD 2025.pdf · matched 99%" (template `{path} · matched {n}%`) |
| `row.received.word` | "Received" |
| `row.needsReview` | "harborline-upload/Harborline Certification PY2025 signed.pdf · uploaded Sep 11 · matched 94%" · "Uploaded – needs review" |
| `row.linked` | "Linked (1)" (template `Linked ({n})`; "—" on requested rows) |
| `row.overdue` | "Overdue" |
| `row.returned` | "Returned · wrong document" (template `Returned · {reason}`) |
| `row.menu` | "Open in Files" · "Replace" · "Unlink" |
| `viewer.fit` | "Fit" · "1 / 5" (template `{page} / {pages}`) |
| `viewer.reveal` | "Reveal (logged)" |
| `strip.match` | "Match 94%" (template `Match {n}%`) |
| `strip.return` | "Return…" |
| `strip.accept` | "Accept" |
| `screening.header` | "Evidence screening · Sep 11" (template `Evidence screening · {date}`) |
| `screening.q.answers` | "Does this answer the request?" |
| `screening.q.period` | "Is it inside the expected period?" |
| `screening.b.answers` | "Yes: Harborline's certification of investment information for PY2025, signed by an authorized officer." |
| `screening.b.period` | "Yes: as of December 31, 2025 and for the year then ended." |
| `screening.c.answers` | "No: this file covers only the 31 participants in BrokerWindow; a schedule of account balances covers every participant." |
| `screening.c.period` | "As of December 31, 2025" |
| `screening.footer` | "Draft follow-up" · "Rerun" (+ ThumbsUp / ThumbsDown) |
| `screening.provenance` | "Screened by Accrued Agent · screener@v3 · 2 s" |
| `c.flaggedRow` | "BrokerWindow Asset Detail 2025.pdf · Wrong document · View · Return" |
| `c.match` | "Schedule of Account Balances ← initial-input/BrokerWindow Asset Detail 2025.pdf · match 62%" |
| `return.reasons` | "Wrong period" · "Wrong entity" · "Incomplete or unsigned" · "Wrong document" · "Other" |
| `empty.notReceived` | "Not received yet" |
| `empty.requested` | "Requested Sep 1 from Dana Kowalski · due Sep 18" (template `Requested {date} from {owed_by} · due {date}`) |
| `empty.remind` | "Remind" |
| `empty.thirdParty` | "Request from third party…" |
| `f.nothingMissing` | "Nothing missing" |

Viewer page (a; seed document with F-04-T25 fixed regions, verbatim): "Keystone Retirement Services" · "BrokerWindow Asset Detail Report" · "Northwind Robotics 401(k) Plan" / "As of December 31, 2025" · "Participant: Gordon Whitfield" · "SSN: •••-••-2281 · Account value: $214,380.50" · "Security | Market value | % of account" · "AAPL — Apple Inc | $75,033.18 | 35%" · "MSFT — Microsoft Corp | $53,595.13 | 25%" · "VTI — Vanguard Total Stock Market ETF | $42,876.10 | 20%" · "BND — Vanguard Total Bond Market ETF | $42,876.09 | 20%" · "Participant: Mei Tanaka" / "SSN: •••-••-6610 · Account value: $168,240.00". b's page 1 / 5: "Harborline Trust Company — Certification of Investment Information" with the sentence "…is complete and accurate as of December 31, 2025 and for the year then ended" lit purple. The 24 request titles and paths are spec.md's, verbatim.

## Links
| From | To (manifest builder) | Planned or live |
|---|---|---|
| "All Audits" | AUD-01 `to.AUD01()` | planned until A-01-T11 |
| Rail Client and rail rows | AUD-02 and its targets (as AUD-02) | planned until A-01-T12 |
| "+ Add" | SHL-14 request composer | per manifest (P-06) |
| "Linked (n)" | SHL-21 | planned (K-04; count only, DV-7) |
| "Request from third party…" | POR-14 invite (R-01) through P-06's delegate endpoint | planned until R-01 S9 |
| "Draft follow-up" (card) | POR-04 comment draft (P-06's sheet; a person sends) | planned (R-01) |
| "Open in Files" (row menu) | FIL-01 | planned (N-01, DV-7) |
| Row click | SHL-08 grammar viewer in the right pane | in-screen |
| Client view of these requests | POR-03 (mirror, not a link) | — |

Inbound: AUD-02 ("Source Documents ›"), AUD-01 (PBC cell), AUD-10 (bridge-letter request). The five designed links of AUD-03 in `handoff-links.json` (AUD-01, SHL-14, SHL-21, POR-14, AUD-02) are named above with manifest IDs `link-contract.test.ts` knows.

## Acceptance
- AUD-03 acceptance: against `audit-source-documents.png`: 536 canvas + 490 viewer, folder bands on #EFEEEB, rows with a sub-line, "Available"-style grammar (word + olive disc) and a selected row; viewer with the olive table header.
- AUD-03 acceptance: group counts read 3 of 5 · 4 of 6 · 3 of 7 · 1 of 4 · 0 of 1 · 0 of 1, which sums to 11 of 24, and the rail matches.
- AUD-03 acceptance: every open row names who owes it and when (Dana Kowalski, Sam Ortiz at Keystone, Harborline, PayGrid, Summit).
- AUD-03 acceptance: the BrokerWindow participant's holdings foot to $214,380.50 and the SSNs are masked `•••-••-2281`.
- AUD-03 acceptance: accepting the certified trust report needs a human click and moves the count to 12 of 24; no agent ever accepts it.
- AUD-03 acceptance: the 62% match state explains, in domain terms, why a brokerage-window detail is not a schedule of account balances.
- AUD-03 acceptance (R2): Linked (n) and the screening glyph appear on every upload row; requested rows show "—" and no glyph.
- AUD-03 acceptance (R2): state b shows two passed checks above the page; the Accept / Return strip stays.
- AUD-03 acceptance (R2): state c shows a flagged card with the Wrong document reason.
- AUD-03 acceptance (R2): counts stay 24 requests · 11 received · 1 needs review · 12 requested.
- A-01 Story 3.3: Return confirms `send_back` with reason `wrong_document`; any message leaves only when a person sends P-06's follow-up.
- A-01 Story 3.4: g's Overdue is derived (nothing stored); f reads "n of n" in every band and "Nothing missing".
- A-01 Story 4.1: "Remind…" lists Dana's 5 open items and sends only on a person's click.

## Figures
| Figure | Foots | Proven by |
|---|---|---|
| Requests | 24 = 11 received + 1 needs review + 12 requested | A-01-T03 fixture assertion; A-01-T10 |
| Groups | 3/5 · 4/6 · 3/7 · 1/4 · 0/1 · 0/1 → 11 of 24 | same |
| Holdings (a) | $214,380.50 = 75,033.18 + 53,595.13 + 42,876.10 + 42,876.09 | scenario test a |
| Accept (b) | 11 → 12 of 24; Trust band 4 → 5 of 6 | scenario test b |
| BrokerWindow (c) | 31 participants | scenario test c |
| Remind (e) | Dana's 5 open items | scenario test e |
| Overdue (g) | 12 requested = 9 due Sep 18 + 2 due Sep 25 + 1 due Sep 30; the 9 show Overdue on Sep 21 | scenario test g |
| All received (f) | 24 of 24 | scenario test f |

## AVOID
Each becomes a test in `AUD-03.test.tsx` ("AUD-03 avoid: …"): gradients in product UI, emoji, saturated blue, heavy shadows, invented colors, lorem ipsum, red for ordinary missing items (only Overdue/Returned use red-tint), dark viewer backgrounds, page thumbnails, unmasked SSNs, the words Accrual/Arc/ACME/Finality/Living Robotics; (R2) the agent accepting or returning a file, screening shown as a match percentage, changing row data or counts, blue, "task" for a to-do.

## Deviations
| ID | What differs from the handoff | Why | Decision recorded |
|---|---|---|---|
| DV-1 | Live rail shows only registered sections (as AUD-02) | Registration-driven rail | A-01 §2.4; DEC-261 |
| DV-3 | Viewer Ana Cruz; c at Sep 9, g at Sep 21 | DEC-15 | A-01 §2.4 |
| DV-7 | "Linked (n)" shows the count only; Unlink and "Open in Files" are planned links in the row menu; Replace uploads a new version on behalf | SHL-21 is K-04; FIL-01 is N-01 | A-01 §2.4 |
| DV-8 | "Remind…" opens P-06's FollowUpSheet with a template-composed body; a person sends | ADR-111; DEC-74 | A-01 §2.4 |
| DV-9 | The export entry in the header "···" and the export sheet are composed from kits | No artboard | A-01 §2.4; the design follow-up in docs/screens/AUD-02.md (A-01-T24, DEC-541) |
| — | The Agent check chip "Agent check: period ✓ · signed ✓ · entity ✓" of the original b is replaced by the C-34 ScreeningCard | revision item 3 | revision.md |
| DV-13 | The 490 viewer is the cockpit dock widened to `--ev-w`, under its 46 Agent · Viewer header (the artboard draws no header) | One cockpit host for AUD-02 and AUD-03 | DEC-421 |
| DV-14 | Rows are composed in the screen from kit parts; the bands are the compact SourceDocGroup (no olive count in f); the 12 px glyph is the 13 px disc | C-02 has no Linked cell, glyph, Overdue/Returned pill or menu (a `ui-kit-component` task) | DEC-421 |
| DV-15 | The ScreeningCard's answers are worded by code; b's two verbatim sentences are not shown; c's reason is the flag's verified citation | DEC-351 | DEC-421 |
| DV-16 | c's pill reads the status word "Uploaded – needs review", not "Match 62% · needs review"; the 62% is in the sub-line and the strip | Status words come from the vocabulary | DEC-421 |
| DV-17 | The Return dialog lists the platform's send-back catalogue, not the artboard's five labels | Content belongs to the catalogue | DEC-421 |
| DV-18 | "Request from third party…" is a dialog over the client contacts with SHL-14's words; the strip and "Request from third party…" follow capabilities (disabled for staff) | No artboard for the picker; C5 grants delegation to senior and above | DEC-422 |
| DEC-348 (seed) | With `--slice portal_pbc`, five of Northwind's rows carry POR-03 i's client title ("W-3 for 2025", "Opt-out elections — auto-enrolled employees", "Pay rate authorizations", "Employee census file — 2025", "Participant complaints log and support"), the list is named "PY2025 Audit requests" and 15 rows are delegated without a grant (DEC-471); `description` keeps AUD-03's words, and the 24 rows and their totals (11 / 1 / 12) are unchanged | The portal handoffs win for the client-facing title only | decision-log DEC-348; TASK-1221 |

## Parity
| Artboard | Tier (A/B/C/D) | Diff % | Notes |
|---|---|---|---|
| e | C (threshold 0.20, maxDiffPixelRatio 3 %) | 2.99 | locked (A-01-T28, measured Thu Oct 29, 2026 after DEC-908 put the audit bar and panes at the handoff's 46 / 115; the rail's 44 rows as AUD-02's) |
| a–d, f, g | C | 5.47 / 4.25 / 6.18 / 12.82 / 5.64 / 3.11 | report-only (d opens on the Return dialog); locked by Fri Apr 30, 2027 once the viewer and dialog regions are masked; SHL-20's card is parity-checked inside b and c |
| host | D | — | audit bar 59, rail 330, canvas 536, viewer 490, rows 52, group bands 32, evbar 44, pills 19, radius 12 |

## Open gaps
- spec.md lists the BrokerWindow row as selected in a and its "Received" grammar; the C5 v1.1 row carries `match_confidence` for the "matched 96%" sub-line (A-01-T10 populates it).
- The original b chip "Agent check: period ✓ · signed ✓ · entity ✓" names three checks; DEC-48 stores two named checks plus file flags, so the ScreeningCard shows two (revision item 3 agrees).
- (A-01-T15) "Source Documents ›" on AUD-02 still opens AUD-02's own canvas; routing it to AUD-03 with the same row is left to the AUD-02 owner (A-01 Story 2.3).
- (A-01-T15) The "Sample-driven · 0" band is drawn from a `counted: false` group; the live aggregate does not return one until A-03, so live it is absent.
- (A-01-T15) The live aggregate returns no `screening` verdict and no row `allowed_actions` yet (A-01-T10 populates `match_confidence` only); the glyph appears live once it does, and the strip follows capabilities.
- (A-01-T16) The staging fixture-to-live swap and the M6 journey step are not done from a local worktree.
