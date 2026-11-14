---
id: SPEC-655
title: C-01 Close engine v1 (read-only) — closes portfolio and record, close plans, monthly intake, close runs, QuickBooks Online hourly read, accounts and schedules, bank reconciliation, review and client questions, flux
status: approved
owner: ayushkbhatia
risk_zone: red
related_adrs: [ADR-004, ADR-005, ADR-007, ADR-014, ADR-020, ADR-027, ADR-031, ADR-040, ADR-041, ADR-043, ADR-045, ADR-050, ADR-052, ADR-071, ADR-078, ADR-090, ADR-136, ADR-137, ADR-138, ADR-139, ADR-140, ADR-145, ADR-150, ADR-151, ADR-160, ADR-161, ADR-164, ADR-186, ADR-321]
related_specs: [SPEC-333]
created: 2026-11-14
updated: 2026-11-14
---

> **Instructions for coding agents**
> - C-01's own SPEC (C-01-T01). The design is `docs/plan/epics/C-01.md` §1 to §8; task rows are
>   `docs/plan/epics/C-01.tasks.csv`. Screens: `$ACCRUED_HANDOFF_DIR` CLS-01…06, 09, 10 and POR-11
>   (the R2 revisions of CLS-01, CLS-02 and CLS-03 win over their specs).
> - Contracts provided: `docs/contracts/closes.md` (C-01-T04, T05), the C9 v2.1 additive section of
>   `docs/contracts/c09-ledger.md` (C-01-T07) and the C5 additive "Transaction questions" (C-01-T24).
> - **Read-only means read-only.** No write method or route reaches QuickBooks Online (CONN-001,
>   ADR-040). Posting (W1, ADR P-16), CLS-07, CLS-08, CLS-11, CLS-12 and CLS-13 are C-02's.
> - Code computes, models judge (ADR-050): every figure is a `Decimal` from a deterministic engine
>   with `engine_version` and `inputs_hash`; model text only cites fact tokens.

## 1. Summary
A CAS firm runs each client's month-end close in Accrued against a read-only, hourly-synced
QuickBooks Online ledger. One close per client-month under a "Monthly close" engagement carries a
six-state status with server gates and an "On hold" side flag; a pinned, versioned close plan
drives monthly requests (published on business day 1) and a code-planned run of procedures, three
at a time, on the P-10 runtime. Code reconciles bank accounts to statement regions, ties schedules
and tests flux on two legs; the Accrued Agent drafts, cites and waits. A person approves an entry
in SHL-10, records it in QuickBooks outside Accrued, and the next sync ties the schedule.
J10 steps 0–7, J16 step 8 and J02 step 7 become walkable by M20 (Tue Oct 31, 2028).

## 2. Gate check (main 61c47b52b, 2026-11-14; DEC-5001)
Checked by P-ID; ADR numbers outside ADR-116…130 read from `docs/adr/backlog.md` (F-02 erratum).

| P-ID / decision | Plan alias | On main | State | What C-01 does |
|---|---|---|---|---|
| P-04 Engagement + work items + gates (DEC-07) | ADR-120 | ADR-136 | accepted | `close` work items under `cas_monthly_close`, G1 + G3 gate policy (T09, T14) |
| P-07 Review grammar (DEC-36) | ADR-133 | ADR-160 | accepted | L1 sign-off with content hash and staleness, one issues service, decision cards (T20, T23, T24) |
| P-35 Suggestions, proposals, Undo (DEC-24, DEC-28) | ADR-126 | ADR-161 | accepted | Agent drafts are suggestions; reclasses are proposals approved in SHL-10 (T21, T28–T30) |
| P-17 `integrations` and write capabilities (DEC-46) | ADR-136 | ADR-150 | accepted (the file reads accepted; the `docs/adr/backlog.md` row still says proposed and is stale) | `connections` stays read-only; no W entry (T16, T17, T48) |
| P-13 Independence and attest rules (DEC-69) | ADR-142 | ADR-164 | accepted | The attest flag drives CLS-01 d and `classify_entry` (attest entries always held) |
| P-32 OCR (DEC-42) | ADR-153 | ADR-321 | accepted | Statement lines with cell boxes for CLS-05 (T22) |
| P-49 Autonomy policy and Auto mode (DEC-50) | ADR-148 | ADR-186 | accepted | Auto mode for monthly closes stays forced off; every run starts from a named person |
| P-29 Busy-season change policy (DEC-68) | ADR-145 | ADR-151 | **proposed** (acceptance: Ayush) | Read as below; S44 builds only additive, default-off, expand-only work |
| P-25 Model-drafted text to clients (DEC-79) | ADR-214 | not drafted | to draft | **Not assumed.** No model text reaches a client from C-01 (template wording only, DV-7) |
| P-16 Client-ledger writes (W1) | ADR-161 | not drafted | to draft (C-02's) | **Not assumed.** No posting; CLS-04 b2/c are C-02's |
| DEC-70 First live ledger | repo ADR-045 | decision log row; `docs/product/discovery/` | decided (QBO default) | QBO is the live ledger (A-02-T26 connector, A-02-T32 conformance) |
| P-36 API conventions | — | ADR-139 | accepted | List envelope, `allowed_actions`, If-Match, `Idempotency-Key`, 501 stubs |
| P-39 per-module registries; P-05 module map (DEC-13) | ADR-124, ADR-121 | ADR-140, ADR-137 | accepted | `closes/registry.py`, per-module matrix and flag files (T02) |
| P-34 status registry (DEC-08, DF-23, DF-31) | ADR-122 | ADR-138 | accepted | Six close states, "On hold" a side flag, no "Closed" (T03) |
| P-06 generalised `visible()` | — | ADR-145 | accepted | Engagement scope for every close list |

**The P-29 reading (recorded, not minuted; solo edition).** ADR-151 is still proposed. Until it is
accepted the plan's proposed option binds: additive, flag-gated code that no live request
executes is dark (a new `closes` file, a route behind a default-off flag, an additive registry
row, an expand-only migration); changing an existing function, route, query or table on a live
path is not. S44's rows are all of the first kind. The Sep 1 – Oct 20, 2028 window rules in C-01
§F11 apply from S48 and are re-checked when ADR-151 is accepted.

**Upstream re-verified (not re-decided).**
- DEC-70: QBO named; the fake QBO and conformance suite are on main (A-02-T26, T32).
- A-02-T33 (QBO production keys and app assessment) is **blocked** (human: Intuit). C-01 builds
  against the fake QBO; the live connection is C-01-T52's gate, not S44's.
- P-11-T36 statement tables are on main (TASK-6526, TASK-6539); T22 does not grow.
- A-08-T20 has not landed `workpapers/compute/flux.py`. If it is still absent at T25 (S48), T25 lands
  `closes/compute/flux.py` with a re-export plan (A-08 OQ-1).
- F-03-T22 `closes.closes` subtype (migration 0089) and F-03-T28 entitlements are on main.
- P-10-T39 `register_run_step` is on main (TASK-6804, TASK-7427).
- F-05-T40 (T2 RecordCockpit) and F-05-T55 (T9 QueueDetailLayout) are on main.

## 3. Open questions (QC-1 to QC-9) — decided with the plan's proposed answers (DEC-5001)
| # | Decision |
|---|---|
| QC-1 | Bank-feed plan rows generate an internal-only request (`client_visible = false`); staff upload the statement on behalf; client-sourced statements stay client requests; no aggregator |
| QC-2 | A close pins its plan version at BD1 publication, not at creation; once pinned it never changes |
| QC-3 | Staff may start runs and incorporate only with the `close_preparer` function on that close |
| QC-4 | CLS-04 b offers "Export entry…" only once QBO's journal-entry import layout is confirmed; until then the note alone (T37 carries the [verify]) |
| QC-5 | Hourly sync 07:00–19:00 firm time on business days; per-firm monthly call budget from the confirmed tier with 80% and 100% alerts |
| QC-6 | CLS-01's four tiles: Approved counts under In review, Locked under Delivered; the Status chip offers all six |
| QC-7 | Past due counts business days on the firm's calendar from `due_on` |
| QC-8 | "Request publish" is a C13 gate kind (`close_plan_publish_requested`) for the engagement's Managers and Partners, plus the notification |
| QC-9 | A client contact assigned to an issue sees only the transaction question in client wording; never the issue, its severity or the agent |

## 4. Acceptance criteria
Condensed from `docs/plan/epics/C-01.md` §3 (the epic's Given/When/Then text is the full form and
wins on any wording). Invariants: **INV-1** the agent never decides · **INV-2** citations and
provenance verified · **INV-3** walls hold · **INV-4** portal scopes isolated · **INV-5** attribution
correct. All money is `Decimal`.

### F1 · Portfolio and close record
- **AC-1** (US-1.1) `/closes?period=2026-08` for Priya renders 22 rows; tiles foot 3 + 11 + 5 + 3 = 22; summary 51 open issues, 2 past due, 3 running.
- **AC-2** (US-1.1) The reconciled figure is code: an account counts when its procedure ties, any required L1 is current and no open issue links to it (Copperleaf 43%, 9 / 21).
- **AC-3** (US-1.1, QC-7) Past due counts firm business days from `due_on` (Copperleaf 4, Bluebird Bakery 2 on Mon Sep 14, 2026).
- **AC-4** (US-1.1) A walled close is absent from rows, tiles and summary; `GET /v1/closes/{id}` answers 404 (INV-3).
- **AC-5** (US-1.2) Tile and chip filters (b, c), Attest filtered-empty "No attest clients this period" (d), skeleton rows (e), row menu Open · Start run · View plan (f).
- **AC-6** (US-1.2) Start run with open requests confirms "Statements not received — start the run anyway?"; no run starts without the click (INV-1).
- **AC-7** (US-1.3) The CLS-02 rail shows Open Issues 7, Documents in Binder 58, Accounts Reconciled 9 of 21, Past Due 4 days, with the planned links (DV-6).
- **AC-8** (US-1.3) Manager or Partner reassignment writes `work_item_assignments` with `close.assignee_changed` in one unit of work; a Senior sees read-only pickers.
- **AC-9** (US-1.4) "In review…" below 21 of 21 answers 409 `accounts_not_reconciled` naming the account; at 21 of 21 with no run in progress the close and its work item move together and `close.status_changed` is emitted.
- **AC-10** (US-1.4, DF-23) "On hold…" keeps the status and sets the side flag with a required reason.
- **AC-11** (US-1.4) Approved, Delivered and Locked answer 409 `transition_not_available` until C-02 registers a guard (fail closed); Not started → In progress is a system transition.
- **AC-12** (US-1.4) An agent principal on any status route gets 403 and `decision.refused_non_human` (INV-1).
- **AC-13** (US-1.5) A Monthly close engagement creates 12 closes 2026-01…2026-12; a 13th for an existing period answers 409; no requests publish before G1 + G3.

### F2 · Close plan
- **AC-14** (US-2.1) Plan v3 lists 21 balance-sheet accounts and 2 income-statement procedures; tally 23 = Manager 8 + Senior 15; 8 requests a month; frequency is a word.
- **AC-15** (US-2.1, INV-5) History reads "Raj Malhotra via Agent · Close Planner" for v1 and Priya for v2 and v3 (DV-4).
- **AC-16** (US-2.2) Draft v4 from v3; a source change reads "Changed"; Raj's action is "Request publish…", which raises one `close_plan_publish_requested` gate and publishes nothing (QC-8).
- **AC-17** (US-2.2) Publish v4 effective 2026-09 confirms "applies from the September 2026 close; August stays on v3"; the published version is immutable (trigger); `close_plan.published` emitted.
- **AC-18** (US-2.2, QC-2) A pinned close never changes plan version.
- **AC-19** (US-2.2) A stale If-Match answers 412 `stale_version` naming the other editor.
- **AC-20** (US-2.3) Four template cards come from DB content imported through `/v1/close-templates:import`; no template text is committed.
- **AC-21** (US-2.3) "Draft from ledger history" starts `close.agent` mode `planner` attributed "Raj Malhotra via Agent"; code profiles the history; the model picks from closed option sets.
- **AC-22** (US-2.3, INV-1) Publish with an unadopted drafted row answers 409 `unadopted_rows`; adoption is a person's click.

### F3 · Monthly intake
- **AC-23** (US-3.1) At BD1 09:00 firm time `RequestPublishWorkflow` pins the plan, generates the close's requests into its `close_intake` binder, emits `close_requests.published`; bank-feed rows are internal-only (QC-1); replay creates nothing twice.
- **AC-24** (US-3.2, INV-2) Upload totals are code with `sheet_cell` citations (21 transfers; 73,166.90 − 1,684.54 = 71,482.36); the summary is mode `intake` text over fact tokens, or "Totals from the file" with the agent off (DV-3).
- **AC-25** (US-3.2) The ScreeningCard reads "Partly" on the Amex period check (g); Rerun shows "Screening…" (h).
- **AC-26** (US-3.3) Incorporate sets `incorporation_state = incorporated` with the person as actor and offers "Re-run affected tasks" for exactly the procedures sourced from that request; Return to client carries a reason code; the agent gets 403 (INV-1).
- **AC-27** (US-3.4, US-3.5) Overdue reminders follow POR-20's 7-day cadence (a person sends); Mark as Done completes the binder and notifies Raj; Undo until the firm acts.

### F4 · Close runs
- **AC-28** (US-4.1) `POST /v1/closes/{id}/runs` requires a live human with `close_run.start`; the plan is code (DEC-57); Run 2 holds 9 procedures in 5 groups, never more than 3 at once.
- **AC-29** (US-4.2, INV-1) An unmatched Square transfer raises a `close_treatment` decision card with code options; the group holds; a person answers; the agent can raise, never answer.
- **AC-30** (US-4.3) A failed procedure reads "Stopped at Shopify…"; Retry runs a new step row.
- **AC-31** (US-4.4) Run completion reads "Complete with exceptions · 9 of 9 · 7 open issues" and notifies preparer and reviewer; Run 1 stays read-only in history.

### F5 · QuickBooks Online read and sync
- **AC-32** (US-5.1) `LedgerSyncWorkflow` pulls only CDC-changed datasets into new immutable snapshots inside business hours; freshness 60 ± 15 minutes; Sync now (Senior and above) is logged.
- **AC-33** (US-5.2) Throttles back off (ADR-043); refused tokens go to Needs reauth and pause the entity; the meter budget pauses scheduled syncs and notifies the firm admin; the kill switch stops calls within one tick.
- **AC-34** (US-5.3) No code path in `connections`, `ledger` or `closes` issues POST, PUT or DELETE to an Intuit host (CONN-001; the write-interception harness).

### F6 · Accounts and schedules
- **AC-35** (US-6.1) The tree foots in code: Asset 539,055.45 = Liability 163,543.05 + Equity 375,512.40; contra balances in parentheses; register rows cite as `ledger_line`.
- **AC-36** (US-6.1) A category change creates a reclass proposal to SHL-10, never a change to the transaction.
- **AC-37** (US-6.2) The Cedar Mutual schedule computes 2,800.00 against GL 3,500.00 → "Ties once posted"; an unexplained difference reads "off 60.00" and raises one review issue.
- **AC-38** (US-6.3, DV-1) Approved AJE-02 shows no Post AJE control; a matching synced journal entry links through `close_entry_recordings` ("Recorded in QuickBooks · JE 48214 · found by sync 10:20"); an ambiguous match asks a person.

### F7 · Bank reconciliation
- **AC-39** (US-7.1) ••4410: 184,236.18 + 6,412.40 − 5,658.08 = 184,990.50 = 184,610.50 + 380.00; difference 0.00; #2281 stale at 193 days; Run 1 reads "off 380.00".
- **AC-40** (US-7.2, INV-2) Each reconciling line traces through `reconciliation_matches` to a statement region verified as a `document_text` citation; low-confidence OCR lines never auto-match.
- **AC-41** (US-7.3, INV-1) Propose AJE shows a code-built draft; a person proposes through `adjustments.api.propose_entry`; the agent cannot propose.
- **AC-42** (US-7.4) L1 with open items answers 409 `open_items`; a later book change computes a new version and the L1 goes stale.
- **AC-43** (US-7.5) An owed statement renders the empty viewer "Statement requested Sep 1" and the book side only.

### F8 · Review and client questions
- **AC-44** (US-8.1) Medium 2 + Low 5 = 7 = Review badge = CLS-02 Open Issues; notes never count; "No open issues." when empty.
- **AC-45** (US-8.2, INV-1) Resolve requires a note; only people resolve, mark not applicable (reason required) or reopen.
- **AC-46** (US-8.3, DV-7) Ask client uses the firm's DB template with code facts; `communications.send` runs its scope check; no agent-drafted wording while P-25 is off.
- **AC-47** (US-8.3, QC-9, INV-4) The client sees only the question's client wording and context line; the answer's attachment fulfils the linked request; client text is wrapped as untrusted before any model reads it.

### F9 · Flux
- **AC-48** (US-9.1) 13 lines tested on adjusted figures; only Payroll (+7,670, 12.5%) and Repairs (+2,560, 400.0%) exceed both legs (10% AND $2,500); year over year shows "—" and "not comparable"; Budget disabled.
- **AC-49** (US-9.2, INV-1, INV-2) Mode `flux` drivers foot to the change in code or the run repairs once then asks; only a Manager or Partner accepts (Senior 403; agent never).

### F10–F11 · Agent, walls, portal, attest, freeze
- **AC-50** (F10, INV-1, INV-5) The agent never changes a status, incorporates, returns, proposes, signs, resolves, accepts, publishes or sends; attribution reads "<person> via Agent"; with `closes.agent` off the run completes on code with template texts.
- **AC-51** (F11, INV-3) Every C-01 list goes through `visible()`; walled objects answer 404 and never appear in counts, search or notifications.
- **AC-52** (F11, INV-4) Portal principals read only granted closes through the portal serializer; responses carry no firm-only field.
- **AC-53** (F11) Attest clients' entries always classify Review required; nothing in C-01 posts for any client.
- **AC-54** (§4.7) Each of `closes.engine`, `closes.portal_requests`, `closes.agent` and `connections.ledger_sync` defaults off; off answers 404 `feature_disabled` after authorising; the `closes` entitlement gates the module independently.

## 5. Task map
| Sprint | Rows |
|---|---|
| S44 | T01 SPEC · T02 protected bundle (red) · T03 status rows and copy registries · T04, T05 closes stubs · T06 consumer tests · T07 C9 v2.1 stub (red) · T08 C9 v2.1 consumer tests (red) · T09 `closes_v1` · T10 `ledger_cas_v1` (red) · T12 close shell |
| S45 | T11 `closes_v2` and `requests_cas` · T13 figure book and fixtures · T14 close kind and status machine · T15 plan service · T16 QBO connector v2 (red) · T33 CLS-01 |
| S46 | T17 `LedgerSyncWorkflow` (red) · T18 ledger read API (red) · T19 intake · T20 run provider · T31 eval suite · T34 CLS-02 · T35 CLS-03 |
| S47 | T21 accounts · T22 reconciliation engine · T24 issues and questions · T28 close tools · T29 `close.agent` v1 (red) · T45, T46, T48 tests · T57 seams |
| S48 | T23 reconciliation service · T25 flux · T26 registrations · T30 modes flux and planner (red) · T36 CLS-09 · T40 CLS-10 · T42 live swap 1 · T52 readiness (red) · T58 `close_receipt` |
| S49 | T32 real evals (red) · T37 CLS-04 · T38 CLS-05 · T39 CLS-06 · T43 live swap 2 · T47, T49 tests |
| S50 | T27 portal read model · T41 POR-11 · T44 CAS slice · T50 parity · T51 journeys |
| S51 | T53 shadow flip pack · T54 shadow support · T55 docs and screen contracts · T56 red docs |

Migrations (expand-only, one per PR, by Thu Aug 24, 2028): T09 `closes_v1`, T10 `ledger_cas_v1`,
T11 `closes_v2` and `requests_cas` (§4.2 of the epic).

## 6. Deviations (recorded in `docs/screens/<ID>.md` by T55)
DV-1 CLS-04 read-only · DV-2 CLS-05 d wording · DV-3 CLS-03 summary label · DV-4 attribution ·
DV-5 board views · DV-6 planned links · DV-7 client wording · DV-8 POR-11 on the C-16 Request kit ·
DV-9 CLS-01 four tiles (epic §2.1).
