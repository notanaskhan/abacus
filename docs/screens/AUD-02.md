# AUD-02 · Audit cockpit (Overview + Source Documents + Agent)

| Field | Value |
|---|---|
| Route and params | `/audits/$auditId` (`$auditId` = the assurance work item, P-04; A-01 §5.1), dispatched by work-item subtype (FS and EBP; SSARS here until AUD-26, DV-5). `?layout=rail\|focus`, `?dock=agent\|viewer`, `?doc=<evidenceVersionId>` (viewer tab), `?section=<key>` (selected rail row; default `source_documents`). Overlays: `?ov=export`, `?ov=export:<exportId>` (O3 export sheet, A-01-T24), `?ov=request:new\|<id>` (SHL-14, P-06). Artboards: `/components/screens/AUD-02?st=a…g` |
| Template and host frame | T2 `RecordCockpit` with the dock (promotes TPL-02): audit bar 59 · rail 330 · canvas 696 · dock 330 · `Wave 1 - Service Lines.dc.html#aud02`; screen kit `kits/Board Specimen.dc.html` |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/AUD-02 Audit cockpit - Overview- Source Documents- Agent/` (README.md, spec.md, revision.md R2; revision wins, DEC-15) · HANDOFF_VERSION 2026-10-21 |
| Epic and tasks | A-01 · contract A-01-T01 (this file); stub A-01-T02; consumer tests A-01-T03; phase service A-01-T05; cockpit L3 (`AuditBar`, `SectionRail`, `BlockedSectionCard`, `DockHost`) A-01-T06; cockpit projection and providers A-01-T09; screen A-01-T12; f frame A-01-T31; export sheet A-01-T24; parity A-01-T28. Dock content of a–e: P-09 on P-10 |
| Manifest status | planned (`routes/manifest/aud.ts`); turns `fixture` with A-01-T12. Built on fixtures by A-01-T12: routed with its path, status kept `planned` for DEC-195's reason (DEC-341) |

Code to come (A-01 §5.2): `src/domain/audits/{AuditBar.tsx, SectionRail.tsx, BlockedSectionCard.tsx, DockHost.tsx, queries.ts, mutations.ts, messages.ts}` (A-01-T06), `src/screens/AUD-02/{index.tsx, scenarios.ts, copy.ts, AUD-02.test.tsx}` (A-01-T12), `src/routes/firm/audits.tsx`, `src/fixtures/handlers/audits.ts`.

## States

AUD-02 has 9 artboards (a–i). The README's viewer column ("Marcus Delaney") loses to revision.md: the viewer is **Hannah Leclerc** for a–g, Omar Haddad for h and Cole Hart for i (DV-3). Clocks are the state labels' times (they win over `rendered`).

| Artboard | Viewer (persona) | Clock | Snapshot | Data condition that produces it | Status |
|---|---|---|---|---|---|
| a | hannah-leclerc | Mon Sep 14, 2026, 9:41 AM CT | E0 + run #4127 | Marcus Delaney's engagement run on Northwind: Trial Balance complete, Materiality blocked on Margaret Okonkwo, Risk Assessment running, two waiting on inputs, SOC 1 queued, Testing not started | fixture (T12: audit bar, rail and canvas; dock masked) until P-09 / P-10 |
| b | hannah-leclerc | 9:20 AM | E0 | No engagement run; every phase row "Not started"; overview pill "Planning" | built (T12, live) |
| c | hannah-leclerc | 9:23 AM | E0 + run #4127 proposed | Plan proposed, waiting for approval in the dock | fixture (T12; dock masked) until P-09 / P-10 |
| d | hannah-leclerc | 9:41 AM | E0 + run #4127 | `?section=materiality` with the section blocked on a decision: the canvas shows `BlockedSectionCard` | fixture (T12) until P-10; the card is A-01-T06 L3 |
| e | hannah-leclerc | 9:58 AM | E0 + run #4127 | The Internal Control step failed (BH-EBP-140 step 8 pack configuration error) | fixture (T12; dock masked) until P-09 / P-10 |
| f | hannah-leclerc | 9:41 AM | E0 + run #4127 (the artboard draws the run's rail and "Started 9:24 AM") | Auto mode toggle pressed: O3 confirm (`autoMode.confirm`); Turn on writes `PUT /v1/engagements/{id}/auto-mode` `{enabled: true, confirmed: true}`; a 403/409 keeps the confirm open with the refusal (DV-12) | fixture (A-01-T31); live only when `/v1/me` reports `engagement_run.auto_mode` (P-10-T39), with no A-01 change (DEC-405) |
| g | hannah-leclerc | 9:41 AM | E0 | No run; sections in the audit-program grammar: idle pills "Ready" / "In progress" replace sub-lines; overview pill "Planning" | built (T12, live) |
| h | omar-haddad (Omar Haddad, Manager) | Mon Sep 14, 2026, 4:05 PM CT | E2 | Harlow & Pike group audit: the "Group" band between Planning and Fieldwork | deferred → A-09 (registers the band through `register_audit_section`) |
| i | cole-hart (Cole Hart, Staff) | Thu Sep 24, 2026, 9:30 AM CT | Sep 24 | Granite Peak FY2026 with the Board on: the ENG-10 board replaces rail, canvas and dock | deferred → K-04 (C14) |

Personas `omar-haddad` and `cole-hart` exist as seats in `fixtures/seed/people.ts`; no persona is added for this screen.

Non-artboard states:

| State | Data condition | Rendering |
|---|---|---|
| Loading | `GET /v1/audits/{id}/cockpit` pending | T2 skeleton (rail rows, canvas rows) |
| Not found | the work item is outside the tenant, behind a wall, or not assurance | 404 (INV-3); no hint that it exists |
| Metadata only | Grace Holloway (firm admin) | audit bar and OverviewCard with F-05's no-access ViewState in the canvas; no document, screening text or export action (ADR-024, DEC-20) |
| AI unavailable | the data boundary refuses AI for a real firm | Agent tab: "AI isn't available for real client data yet" (DF-04, DV-2) |
| Unregistered section | a rail row's section has no registered state provider | the row is hidden (fails closed, never a fake state; DV-1) |
| Flag off | `audits.cockpit` off | F-05 flag-off ViewState; the legacy board stays until A-01-T21 |
| Archived | the work item is archived | read-only: every write answers 403 `archived_write`; record controls absent |

## API
| Read or write | Endpoint | Shape | Matrix action | allowed_actions and read-only reasons per role |
|---|---|---|---|---|
| read | `GET /v1/audits/{work_item_id}/cockpit` | `AuditCockpitOut`: `audit_bar` (`title`, `methodology_label`, `run_started_at` nullable, `auto_mode` nullable), `overview` (`client_name`, `name`, `period_label`, `pill` C2 `audit_engagement`), `bands[]` (`key` `overview`\|`planning`\|`group`\|`fieldwork`\|`completion`\|`reporting`, `label`, `collapsed`, `rows[]`), rows `AuditSectionRowOut` (`key`, `title`, `work_item_ref`, `state` C2 `audit_section` nullable, `grammar` `sub_line`\|`idle_pill`\|`link`, `sub_line` text, `route` manifest ID, `link_status` `live`\|`planned`, `blocked_on` nullable), `dock_tabs[]` (`agent`\|`viewer`), `phase_mode` `recorded`\|`derived`, `read_only_reason`, `version`, `allowed_actions` | `engagement.read` | `allowed_actions` from `assurance.record_phase`, `engagement.update`, `export.create`, `agent.pause`; empty for metadata-only roles and archived work items |
| read | `GET /v1/audits/{work_item_id}/source-documents?binder=&q=&sort=missing_first\|received_first` | `SourceDocumentsOut`: `received`, `total`, `needs_review`, `requested`, `groups[]` (`category`, `label`, `received`, `total`, `rows[]`) | `request_item.read` | as P-06 |
| write | `PATCH /v1/audits/{work_item_id}/profile` `{ebp_plan_kind, limited_scope_103a3c, standards_set_id, seen_version}` | `AuditProfileOut` | `engagement.update` | EP, manager; 409 `stale_version` |
| write | `POST /v1/audits/{work_item_id}/phase` `{to, reason?}` | `AuditPhaseOut` | `assurance.record_phase` | EP, manager; human only; 409 `phase_backward`, `phase_skip`, `phase_follows_gate` |
| read | `GET /v1/engagements/{id}/activity`, `GET …/agent` (agents, unchanged) | v1 engagement-agent activity for the Agent tab (DV-2) | as owned | — |
| write | `PUT /v1/engagements/{engagement_id}/auto-mode` `{enabled, confirmed: true}` (P-10-T39; not in the OpenAPI document yet, named on the generated client by `domain/audits/mutations.ts`, DEC-405) | any body; the client keeps the value it sent | `engagement_ai.configure` (P-10); the switch renders on `/v1/me`'s `engagement_run.auto_mode` | Manager+; 403/409 = refused (real firm, Season 1, P-10 AC-E3); agent deny |
| write | `POST /v1/engagements/{id}/agent/pause` (unchanged) | "Paused by Marcus Delaney" | `agent.pause` | dock header menu "Pause agent"; an agent context 403 |

Dock content of a, c, d, e (RunCard, transcript, ToolCards, plan approval, Retry, "Fix in Knowledge →", "Sign off run") reads C6 v1 / P-10's `engagements.run` and is out of scope (A-01 §2.3). The contract is `docs/contracts/audits-cockpit.md` (A-01-T02).

## Status
- `audit_engagement` for the overview pill: `planning` "Planning" (b, g), `processing` "Processing" (a, c, d, e; derived from an active C6 engagement run, DV-11).
- `audit_section` for rail rows (sub-line grammar while a run is active, idle-pill grammar otherwise): `draft_ready` "Complete · 9:26 AM" (olive ✓, context `sub_line`), `blocked_on_decision` "Blocked on a partner decision" (amber triangle, amber-ink sub-line, the only amber-ink), `running` "Running" (ink-2 spinner), `waiting_on_inputs` "Waiting on inputs" (half disc; idle pill "In progress"), `queued` "Queued" (ring), `not_started` "Not started" (ring) + "Begin…", `failed` "Failed — see run" (brick ✕), `ready_to_run` "Ready" (idle pill green-tint), `in_progress` "In progress" (idle pill state). Every disc carries text, never colour alone.
- `request` for the canvas rows: `received` "Received ✓" (green 19h), `requested` "Requested" (ink-3 + 14 px ring), `uploaded` "Uploaded – needs review" (amber).

## Copy
Copy keys live in `screens/AUD-02/copy.ts` (screen) and `domain/audits/messages.ts` (L3). Verbatim from spec.md and revision.md.

| Key | String |
|---|---|
| `bar.back` | "All Audits" |
| `bar.title` | "PY2025 Employee Benefit Plan Audit" (seed: the work item's name) |
| `bar.methodology` | "BH Audit Methodology · EBP v3" (the engagement's pinned methodology version) |
| `bar.started` | "Started 9:24 AM" (template `Started {time}`; C6 runs only, DV-11) |
| `bar.autoMode` | "Auto mode" |
| `bar.viewToggle` | "Rail" · "Board" (K-04) |
| `rail.header` | "Overview" |
| `overview.title` | "Northwind Robotics 401(k) Plan" |
| `overview.sub` | "PY2025 · Northwind Robotics, Inc." |
| `band` | "Overview" · "Planning" · "Fieldwork" · "Completion" · "Reporting" (· "Group" for group engagements, A-09) |
| `overview.rows` | "Client" / "Northwind Robotics, Inc." · "Methodology" / "BH Audit Methodology · EBP v3" · "Standards set" / "GAAS nonissuer · AU-C 703" · "Source Documents" / "11 of 24 received" · "Team" / "MO · TW · HL · MD · AC" · "Activity" |
| `section.titles` | "Trial Balance" · "Materiality" · "Risk Assessment" · "General Audit Planning" · "Internal Control" · "Service Organizations & SOC 1" · "Sample Selection" · "Testing" · "Financial Statements" (Reporting; row menu "Disclosure checklist & tie-out (AUD-20)") |
| `section.subLines` | "Complete · 9:26 AM" · "Blocked on a partner decision" · "Running" · "Waiting on inputs" · "Queued" · "Not started" · "Failed — see run" |
| `section.pills` | "Ready" · "In progress" (g) |
| `section.begin` | "Begin…" |
| `canvas.title` | "Source Documents" |
| `canvas.add` | "Add" |
| `canvas.search` | "Search" |
| `canvas.missingFirst` | "Missing first" |
| `doc.received` | "Received ✓" |
| `doc.requested` | "Requested" |
| `doc.needsReview` | "Uploaded – needs review" |
| `groups` | "Plan documents · 3 of 5" · "Trust / Recordkeeper Reports · 4 of 6" · "Census & Payroll · 3 of 7" · "Form 5500 & SOC 1 · 1 of 4" · "Cash · 0 of 1" · "Compliance & other · 0 of 1" (template `{category} · {received} of {total}`) |
| `blocked.title` | "Waiting on Margaret Okonkwo" (template `Waiting on {person}`) |
| `blocked.body` | "Planning materiality is reserved to the engagement partner." |
| `blocked.action` | "Open decision" (planned link while SHL-11 / AUD-07 are unbuilt; announced as unavailable) |
| `dock.tabs` | "Agent" · "Viewer" |
| `dock.signOffRun` | "Sign off run" (P-09; renders only with its capability) |
| `dock.ready` | "Ready to run 14 workpapers across 5 levels" · "Run" (b; P-10) |
| `dock.planReady` | "Plan ready — approve?" · "yes, run it" (c; P-09) |
| `dock.failed` | "Pack configuration error: BH-EBP-140 step 8 points to a SOC 1 bridge-letter template that EBP v3 does not include. No evidence written." · "Retry" · "Fix in Knowledge →" (e; P-09) |
| `dock.aiUnavailable` | "AI isn't available for real client data yet" (DF-04) |
| `dock.pause` | "Pause agent" · "Paused by Marcus Delaney" (template `Paused by {person}`) |
| `autoMode.confirm` | "Turn on Auto mode? Agents will dispatch each level without waiting for plan approval. Decisions reserved to people still wait." · "Cancel" · "Turn on" (f; A-01-T31) |
| `autoMode.refused` | "Auto mode isn't available for client data yet" (f, the server's refusal; ADM-04h's reason, SPEC-349 AC-35, ADR-186 §6; DV-12) |
| `composer.placeholder` | "Message" (P-09) |

Canvas rows (seed, verbatim from spec.md): the 24 Northwind requests with their `initial-input/…` and `harborline-upload/…` paths, 11 "Received ✓" (3 + 4 + 3 + 1), the certified trust report "Uploaded – needs review", 12 "Requested". Dock transcript strings of a ("Run projection · 14 workpapers · 5 levels", the narration cards with $16,812,400.00 = $16,500,000.00 + $312,400.00 described as unadjusted) belong to P-09's SHL-13 contract and are recorded here only for parity.

## Links
| From | To (manifest builder) | Planned or live |
|---|---|---|
| "All Audits" | AUD-01 `to.AUD01()` | planned until A-01-T11 |
| "Source Documents ›" | AUD-03 `to.AUD03({ auditId })` (dock switches to Viewer) | planned until A-01-T15 |
| A document row | SHL-08 viewer in the dock (`?dock=viewer&doc=`) | planned until A-01-T12 (P-03 viewer) |
| "Add" | SHL-14 request composer (`?ov=request:new`, prefilled work item and category) | per manifest (P-06) |
| Client › | CLI-02 | per manifest (P-07) |
| Methodology › | KNW-03 | planned (text without a chevron, DV-1) |
| Standards set › | KNW-04 | planned (text without a chevron, DV-1) |
| Team › | ENG-05 | planned |
| Activity › | AUD-29 | planned (text without a chevron, DV-1) |
| Trial Balance | AUD-06 | planned (A-02) |
| Materiality / "Open decision" | AUD-07 with SHL-11 | planned (A-04, P-04) |
| Risk Assessment · General Audit Planning · Internal Control · Service Organizations & SOC 1 · Sample Selection | AUD-05 · AUD-04 · AUD-09 · AUD-10 · AUD-11 | planned (A-03, A-04) |
| Financial Statements (Reporting) / row menu | FSP-01 / AUD-20 | planned |
| A ToolCard | WB-09 run trace | planned (P-09) |
| Settings gear | ENG-11 | planned (K-04) |
| Group band rows (h) | AUD-31 · AUD-32 / AUD-33 · AUD-34 · AUD-35 | planned (A-09) |
| Board specimen tooltips | SHL-12 · TPL-20 · ENG-01 · AUD-36 | planned / per manifest |

Inbound: AUD-01 (row), SHL-02, HOME-01, HOME-02, ENG-02. All 27 designed links of AUD-02 in `handoff-links.json` are named above with manifest IDs `link-contract.test.ts` knows.

## Acceptance
- AUD-02 acceptance: side by side with `audit-evidence.png`: 59-px audit bar, 330 rail, 696 Source Documents canvas, 330 Agent dock; the same row heights, type sizes and Received ✓ pill.
- AUD-02 acceptance: rail sub-lines read exactly "Complete · 9:26 AM", "Blocked on a partner decision", "Running", "Waiting on inputs", "Queued", "Not started", each with its matching disc.
- AUD-02 acceptance: "11 of 24 received" equals the Received ✓ pills (3 + 4 + 3 + 1); the group counts sum to 24.
- AUD-02 acceptance: the run projection sums to 14 (1 + 5 + 1 + 4 + 3), the same number as the idle state's "Ready to run 14 workpapers" (fixture; P-09).
- AUD-02 acceptance: the dock's amounts tie: $16,812,400.00 = $16,500,000.00 + $312,400.00, and are described as unadjusted (fixture; P-09).
- AUD-02 acceptance: the agent proposes and continues; it never decides. Margaret Okonkwo is named as the decider.
- AUD-02 acceptance: the overview pill reads "Processing" while the run executes; the toggle reads "Auto mode".
- AUD-02 acceptance: the failed-step state (e) reads exactly "Pack configuration error: BH-EBP-140 step 8 points to a SOC 1 bridge-letter template that EBP v3 does not include. No evidence written." on the Internal Control run, with Retry and "Fix in Knowledge →".
- AUD-02 acceptance (R2): Rail · Board and the gear sit in the audit bar; states a–g keep their rail, canvas and dock (both render only with K-04's capability).
- AUD-02 acceptance (R2): Financial Statements opens FSP-01; AUD-20 stays reachable from the row menu.
- AUD-02 acceptance (R2): frame h's Group band matches §9.2 (deferred to A-09).
- AUD-02 acceptance (R2): frame i's column counts match §9.8.1 at 24 Sep, 9:30 AM (deferred to K-04).
- A-01 Story 2.1: no Run, Begin…, Sign off run or Auto mode control renders without its capability in `allowed_actions` / `/v1/me`.
- A-01 Story 2.2: the live rail renders registered rows only; a missing provider hides the row; every disc carries text.

## Figures
| Figure | Foots | Proven by |
|---|---|---|
| Source Documents | 11 of 24 = 3 + 4 + 3 + 1 received; groups 5 + 6 + 7 + 4 + 1 + 1 = 24 | A-01-T03 fixture assertion; scenario tests b, g |
| Run projection | 14 = 1 + 5 + 1 + 4 + 3 | scenario test a (fixture) |
| Trial balance tie | $16,812,400.00 = $16,500,000.00 + $312,400.00 | scenario test a (fixture; P-09 owns the live text) |
| Team | MO · TW · HL · MD · AC (5) | scenario test b |

## AVOID
Each becomes a test in `AUD-02.test.tsx` ("AUD-02 avoid: …"): gradients in product UI, emoji, saturated blue, heavy shadows, invented colors, lorem ipsum, colored row backgrounds for status, the agent saying it approved or decided anything, "Auto sign-off", the words Accrual/Arc/ACME/LSA/Living Robotics; (R2) a Group band on non-group engagements, the Board recording anything a person has not done, settings in a modal, changing states a–g beyond items 1–2, blue, "task" for a to-do.

## Export sheet design follow-up (A-01-T24, DV-9)

Composed from kits; no artboard exists. Recorded for the PF review and as a DF row request to chapter 09 (to mint): "AUD-02/AUD-03 O3 export sheet and record-mode dialogs have no artboard".

- **Entry points:** "Export binder…" in the canvas header's "···" menu (AUD-02; AUD-03's header "···" is the same entry), shown only with `export.create` in the cockpit's `allowed_actions`; `?ov=export` and `?ov=export:<exportId>` open the sheet. "Record phase…", "Record release…", "Record archive…" sit in the same menu's second group while `phase_mode` is `recorded` and the person holds `assurance.record_phase`.
- **Options:** "Include files awaiting review" (off), "Include the audit trail" (on); every PBC binder of the work item. Footer: "Needs a recent sign-in · Undo for 10 seconds", Cancel, Export.
- **Step-up:** a 403 from create or download opens the shell's "Confirm it's you" (ADR-030); nothing is exported.
- **States (C2 `engagement_export`):** Queued, Packaging… (with "Packaging the binder. You can close this sheet; it keeps going."), Ready ("Download · 12 files · 1.2 MB · expires Mon Sep 21"), Export failed (the failure code in words), Expired (the 7 days, or "A file in it was withdrawn by the client, so the package was removed."), Undone. The sheet polls every 3 s while open and the export moves (P-15).
- **Undo:** the C-21 Undo toast "Export requested" for 10 s; Undo voids the grant (`POST /v1/exports/{id}/undo`).
- **Record dialogs:** Dialog 400s in local state; release and archive need a fresh second factor (step-up on 403); the contract's refusals read in words.

## Deviations
| ID | What differs from the handoff | Why | Decision recorded |
|---|---|---|---|
| DV-1 | Live rail shows only sections whose providers are registered (Overview links and Source Documents from A-01; Trial Balance from A-02); fixtures register every row so a–g keep parity. Overview rows whose target is unbuilt (Methodology, Standards set, Activity) render as text without a chevron | A "Not started" row for work Accrued cannot run would mislead a pilot | A-01 §2.4; DEC-261 |
| DV-2 | Agent tab = the v1 engagement-agent activity list, read-only, with "Pause agent" in the dock header menu; DF-04's AI-unavailable state; Notes tab hidden | Run engine and dock UI are P-09/P-10 | A-01 §2.4 |
| DV-3 | Viewer Hannah Leclerc for a–g (README's Marcus Delaney loses); h Omar Haddad 4:05 PM; i Cole Hart Thu Sep 24, 9:30 AM | DEC-15 | A-01 §2.4; DEC-260 |
| DV-4 | The overview pill moves in record mode until the gate providers are registered | G4–G5 providers arrive later | A-01 §2.4; DEC-262 |
| DV-5 | SSARS work items use this cockpit without a Planning band | AUD-26 is A-08 | A-01 §2.4 |
| DV-9 | "Export binder…" and the record-mode entries sit in one "···" menu on the canvas header (not the layout chip: the audit bar's right cluster is the kit's, and the chip toggles the dock), and the O3 export sheet and record dialogs are composed from kits (C-13 Menu, O3 SheetModal, C-06 pills, C-21 Undo toast, the shell's step-up) | No artboard (ADR-036) | A-01 §2.4; design follow-up A-01-T24 (below), DEC-541; DF row requested from chapter 09 |
| DV-11 | "Started 9:24 AM" and "Processing" render only for C6 engagement runs | Engagement runs start with P-10 | A-01 §2.4 |
| DV-12 | f's server-refusal state (a real firm, Season 1) keeps the O3 confirm open and replaces its text with "Auto mode isn't available for client data yet"; Cancel closes it and the switch reads off | The handoff draws no refusal state and AUD-02 has no copy for it; the string is ADM-04h's reason for the same rule (SPEC-349 AC-35, ADR-186 §6), never invented copy | A-01-T31; DEC-405 |
| — | h (Group band) deferred to A-09 and i (Board) to K-04, recorded here, not missing | Owning epics | A-01 §2.3 |
| — | f is built in fixture mode by A-01-T31 and hidden live until `engagement_run.auto_mode` exists | ADR P-49 / DEC-50 | A-01 §2.3 |

## Parity
| Artboard | Tier (A/B/C/D) | Diff % | Notes |
|---|---|---|---|
| b, g | C (threshold 0.20, maxDiffPixelRatio 3 %) | 3.13 / 3.14 | report-only: measured Thu Oct 29, 2026 with the dock masked (`[data-cockpit='dock']`), the audit bar at the window's edges, the rail's Overview band and the 44 rows (DEC-908). What remains: the Source Documents order (the handoff's static frame lists received rows first under "Missing first"; the screen sorts as the chip says, DEC-341), the OverviewCard about 3 px shorter, and the bar controls the viewer's capabilities hide (Auto mode, Rail · Board, gear, Add). A-01-T33 (S34, DEC-909) locks them or records why not |
| a, c, d, e | C | 3.19 / 3.13 / 1.09 / 3.19 | report-only with the dock masked until P-09-T18 locks SHL-13; A-01-T33 (S34, DEC-909) then unmasks and locks them (d passes 3 % masked) |
| f | C | 6.01 | report-only (fixture, A-01-T31; dock masked as a, c, d, e; the confirm open as in `AUD-02f.png`) |
| h, i | — | — | deferred to A-09 / K-04 |
| host | D | — | toolbar 46, audit bar 59, rail 330, canvas 696, dock 330, pane header 46 with a 14.5/500 title, rows 44, pills 21/19, radius 12; masks: spinners |

TPL-02's specimen (F-05-T51) stays green: A-01-T06 composes on it and changes no kit default.

## Open gaps
- The README names Marcus Delaney as the viewer; spec and revision name Hannah Leclerc (decided: revision wins, DV-3).
- The spec's interactions route "Begin…" to a dock plan proposal, which needs P-10's run engine; until then "Begin…" never renders live (A-01 Story 2.1).
- The dock tab strip ("Agent · Viewer") is not drawn in any artboard (the dock header shows only "Agent"); DockHost uses the F-05 tabs grammar in the dock header and the tabs are a tablist (A-01 §5.6).
