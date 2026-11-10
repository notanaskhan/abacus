---
id: SPEC-651
title: T-05 entity return workspace (TXP-00, 01, 02, 05, 06, 07, 10, 11) and the workbook engine
status: draft
owner: ayushkbhatia
risk_zone: amber
related_adrs: [ADR-237, ADR-050, ADR-052, ADR-110, ADR-005, ADR-007, ADR-031, ADR-090, ADR-233, ADR-234]
related_specs: [SPEC-401, SPEC-641, SPEC-647, SPEC-649]
created: 2026-11-10
updated: 2026-11-10
epic: T-05
task: T-05-T01 (TASK-6701)
---

# SPEC-651 · Entity return workspace and the workbook engine

> **Instructions for coding agents**
> - The design is `docs/plan/epics/T-05.md` §1 to §8; rows are `docs/plan/epics/T-05.tasks.csv`.
>   The acceptance criteria below are the epic's §3, numbered here (AC-n.m: story n, criterion m)
>   and adopted verbatim as the spec of record. Where the epic's later revision differs, it wins
>   and this file is corrected.
> - Screen contracts: `docs/screens/TXP-00.md`, `TXP-01.md`, `TXP-02.md`, `TXP-05.md`, `TXP-06.md`,
>   `TXP-07.md`, `TXP-10.md`, `TXP-11.md` (57 artboards). Contract: `docs/contracts/tax-workbook.md`
>   (T-05-T06). Formula grammar: ADR-237 (P-69; proposed, acceptance Ayush's, DEC-3016).

## Scope
- Eight P0 screens, 57 artboards: TXP-00 (5), TXP-01 (6), TXP-02 (9), TXP-05 (8), TXP-06 (6),
  TXP-07 (8), TXP-10 (7), TXP-11 (8). No revision files exist; letters are the handoff READMEs'
  artboard tables. Every letter maps to a fixture scenario, an endpoint set and a parity tier in
  its screen contract (AC-0).
- Modules: `tax` (amber; `compute/entity/` E1, E5, E6, E7), `workpapers` (amber; `compute/formula.py`,
  `dag.py`, `tieouts.py`: E13), consumers of `ledger`, `adjustments`, `review`, `agents`, `evidence`.
- Flags (T-05-T04, default false): `tax.entity_workspace`, `tax.workbook_run`, `tax.entity_agents`.
  Entitlement `tax.entity_returns` (`requires_review: true`).
- Out of scope: TXP-03/04/08/09/13 and engines E3, E4, E8, E9, E10–E12 (T-06); TXP-12, TAX-01/02
  (T-02); TAX-05 to TAX-08 (T-04); filed forms and K-1 PDFs (DEC-78); e-file (R-04).

## Artboard map (AC-0)
- **AC-0** Every artboard letter of the eight screens maps to one fixture scenario (T-05 §5.3), one
  endpoint set (T-05 §4.3) and one parity tier (T-05 §5.4) in its `docs/screens/TXP-xx.md`, and
  each screen adds loading, not-allowed (404, INV-3) and flag-off rows.
- Parity: Tier D blocking on every artboard (subbar 42, tabsbar 50, control bar 44, tally strip 52,
  pane header 46, grid column-letter row 20, row numbers 34); Tier C report-only on all 57, locks
  proposed for TXP-02 a, TXP-05 a, TXP-07 a and TXP-11 a; Tier B for the `WorkbookGrid` specimen.
- Personas and clocks: Olivia Brandt (TXP-00, 02, 11), Samuel Ito (TXP-01, 05, 06, 07, 10); demo
  clock Mon Sep 14, 2026, 9:24 AM CT except TXP-00 b and TXP-10 d (9:52), TXP-10 c (9:51),
  TXP-01 c (9:40), Run 1 states TXP-00 d/e (Sep 8, 10:02 AM) and TXP-00 c (Jun 2).

## DF-34 resolutions
- Schedule L follows pack 08: account 1200 → L5, the mortgage → L18, account 2000 split from 2050.
- Sheet 08 is States; sheets 01–09 are 01 Trial Balance, 02 Fixed Assets, 03 Liabilities,
  04 Partner Txns, 05 Capital, 06 Schedule K, 07 M-2, 08 States, 09 K-1s.
- Capital columns are Tax · 704(b) · Book (tax basis), never GAAP.
- Ridgeline open issues read 11, decrement to 10 after TXP-10 d (T-05), and to 9 with TXP-09 e
  (T-06). Canonical name "Ridgeline Property Partners, LP".

## Deviations
- Import-mode steps: `depreciation_register`, `bonus_eligibility`, `apportionment_ptet` and
  `state_k1s_k3s` read the firm's report (hostile parse, cited `engine_import` cells) or keyed
  cells until T-06's native engines (epic §2.2).
- TXP-12 is T-02's screen; T-05 links to it and writes only draft K-1 values into `k1_packages`.
- Schedule K and capital are read models over workbook cells (`row_key`/`col_key`), not tables
  (epic OQ-8).
- TXP-06 b's "Edit rules" link is not built; TXP-06 a2's handoff viewer (Meera Shah) is the outlined
  series, the persona is Samuel Ito.

## Acceptance criteria
Invariants asserted everywhere (F-04 `assertInvariants`): INV-1 the agent never decides; INV-2
every citation shown is verified; INV-3 walls hold; INV-4 portal scopes are isolated; INV-5
attribution is correct.

### F1 · Entity return shell and form-family dispatch (TXP-00 rail, all tabs)

*As Olivia, I want an entity return to open on its Agent tab with the reviewer's tabs in senior-reviewer order.*
- **AC-1.1** *Given* `tax.entity_workspace` on and a `tax_return` work item with `form = '1065'`, *when* Olivia opens `/tax-returns/$returnId`, *then* the route dispatches to the entity layout and TXP-00 a renders; a 1040 or 1041 still opens TAX-02 (T-02), and with the flag off the 1065 opens TAX-02's coordination view as today.
- **AC-1.2** *Given* the Review toggle off, *then* Group A reads "Agent · Issues 11 · Workpaper · Review · Intake · Activity", regular and centred; *when* Review is on, *then* Group B shows Summary · Financials · Fixed Assets · M-1/M-3 · Schedule M-2 · Schedule K · Capital Accounts · Basis · States, and the four P1 tabs (Fixed Assets, M-1/M-3, Basis, States) render as planned until T-06 (hidden in production by the flag, "Not built yet" in fixture builds).
- **AC-1.3** *Given* a slug that is not valid for the form (for example `/review/provision` on a 1065), *then* `beforeLoad` redirects to the Agent tab.
- **AC-1.4** *Given* the rail, *then* General Information reads the profile in §1 with the EIN masked; *when* a member with `tin.reveal` clicks Reveal on a partner TIN, *then* step-up MFA runs, the value shows for 30 seconds through P-12's logged reveal, the audit row stores the field and the user but never the value (DEC-60), and an offshore user sees no Reveal control (403 if called).
- **AC-1.5** *Given* the subbar, *then* it shows "☰ Checkpoints ⌄" (TAX-07/SHL-16, T-04), the T-01 sync chip ("Not yet exported", disabled with "Map every account first" while Unmapped > 0), the centred title with the state pill "In review · Partner" (context label "Working" while preparing, T05), and Assistant (TAX-08).

### F2 · The workbook run (TXP-00 a–e)

*As Olivia, I want the agent to build the workbook from the shoebox and show which task raised which open item.*
- **AC-2.1** *Given* `tax.workbook_run` on and no prior run, *then* TXP-00 c shows every row with an empty ring "Not started" and the primary ▶ Run; *when* Olivia clicks it, *then* `POST /v1/tax-returns/{id}/workbook-runs {scope: "all"}` answers 202 with a run ID, the run plan is the code plan `tax.entity_workbook` (DEC-57, no model plans it), and the canvas switches to the running card.
- **AC-2.2** *Given* a running run, *then* TXP-00 b shows "7 of 10", "Started 2 minutes ago", at most three rows spinning (ink-2, never amber), a live dot and the bottom running pill, all from SSE run events (C6 v2) with a polling fallback; running and waiting differ by glyph and text, not only colour.
- **AC-2.3** *Given* the §706(d) convention is not determinable from the cited agreement, *when* `interim_closing_706d` starts, *then* the run raises a P-10 run question (TXP-00 d, "Waiting on 1 answer") with options computed by code from Reg. §1.706-4 and a recommended option with a cited reason; branches that do not depend on it continue; *when* Olivia answers Monthly, *then* the branch resumes and the answer is attributed to her; Skip leaves the step at Needs attention with a review-point issue.
- **AC-2.4** *Given* the QuickBooks Online connection health is `needs_attention` (token expired), *when* `import_trial_balance` runs, *then* the step fails with class `connection_needs_attention`, the card reads "Stopped at Import trial balance", and Retry, Reconnect and View run (WB-09) are offered (TXP-00 e).
- **AC-2.5** *Given* Run 2 completes, *then* TXP-00 a reads "Run 2 · Sep 10, 3:31 PM · finished 4:12 PM · 10 of 10 · 11 open items", the per-row counts 1 + 1 + 2 + 4 + 1 + 2 = 11 equal the Issues badge, and each count opens TXP-10 filtered to that step; "View work" opens TXP-11 at the step's sheet.
- **AC-2.6** *When* Olivia chooses Run ⌄ → Re-run group on *Partner transactions & capital*, *then* only that group and its dependents (the K-1 steps) run, every human-edited cell is kept (kept-on-rerun 1.0), and a new workbook version is created as a checkpoint.
- **AC-2.7** *Given* the run history menu, *when* Olivia picks Run 1, *then* the canvas shows that run read-only.
- **AC-2.8** *Given* a partnership without both §7216 consents (`use` and `ai_disclosure`, signed for the partnership; OQ-2), *when* the run reaches a model-backed step, *then* that step waits on inputs with "§7216 AI consent — Ridgeline (1 of 2 signed)", every deterministic step still runs, and no model call is made (`consent_7216`, fail closed).
- **AC-2.9** *Given* an agent principal, *when* it calls the run start route, *then* 403 (`workbook_run.start`, agent deny).

### F3 · TB → TTB, journal entries and form-line mapping (TXP-02)

*As Samuel, I want the trial balance carried to the tax trial balance with every layer footing and every mapping judgment approved by me.*
- **AC-3.1** *Given* Run 2, *then* TXP-02 a lists 28 accounts with PY, UTB, AJE, RJE, ATB, TJE and TTB columns, "$" on every cell, each column footing to $0 (tally "tie"), the balance-sheet tie 17,914,500 = 11,048,300 + 6,866,200 (b) and the capital tie 5,960,000 + 250,000 + 1,256,200 − 600,000 = 6,866,200; numbers are never truncated (horizontal scroll).
- **AC-3.2** *When* Samuel clicks AJE-1's amount, *then* the O2 drawer shows the entry lines, the memo, the source "Cook County second-installment bill → 2025 Binder" with a verified citation, and "Approved by Samuel Ito · Sep 9" (a3). TJE-1 reclasses 6,200 to Schedule K line 18a with net zero (C8 `tje` layer).
- **AC-3.3** *When* Samuel clicks any amount, *then* SHL-09 shows its workbook address (`01 Trial Balance!I18 = F18+G18+H18`, a2).
- **AC-3.4** *Given* the Run 1 snapshot, *then* account 1300 shows "Map…", the Unmapped tally reads 1 (Check) and filters to it, and the sync chip is disabled with its reason (e); *when* Samuel opens the line picker (e2, O1 300 with search over the published TY2025 1065 set) and picks a line, *then* a mapping proposal is created; *when* he approves it in SHL-10, *then* Unmapped becomes 0 and the export gate opens; an agent or a preparer-only member gets 403 on the approval.
- **AC-3.5** *Given* the mapper suggestion for an unmapped account, *then* it carries the account code and name only, never an amount (ADR-050), its output is one of the published form-line keys or "abstain", and it lands as a proposal with the rationale; nothing maps until a person approves.
- **AC-3.6** *Given* Grouped by Form 1065 line (d), *then* subtotals show Schedule L, Form 8825 (by property), Schedule K, M-2 and M-3, computed by code with server totals.
- **AC-3.7** *Given* the Building state (f), *then* tallies read Pending and rows are skeletons while `import_trial_balance` runs.

### F4 · The numbered workbook and its formula engine (TXP-11)

*As Olivia, I want to open the exact cell an issue points at, see its formula and sources, edit or cite it, and open the workbook in Excel.*
- **AC-4.1** *Given* the M-2 issue, *when* Olivia opens it from TXP-10, *then* TXP-11 a selects `05 Capital!H12`, the name box reads H12, the formula bar reads "(empty) — expected ='06 Schedule K'!C31 × 25% → 1,550", the linked-issue chip shows, cited cells H8:H12, J13 and J15 carry the purple tint, and the footer reads "05 Capital!H12 · empty · Cited by 1 issue · Evidence: 06 Schedule K!C31 · Municipal bond fund statement (Harborline, Dec 2025) p. 1".
- **AC-4.2** *Given* any row of 05 Capital, *then* D + E + F + G + H + I = J (crossfoot) and columns D through J foot; `I18 = F18+G18+H18` on sheet 01 evaluates to (94,000).
- **AC-4.3** *When* Olivia double-clicks H12 and saves 1,550 with Enter, *then* `PUT …/workbook/cells/05!H12 {value, expected_version}` writes through `review.api.record_value` (`value_source = human`), recomputes J12, J13 and the tie, saves the checkpoint "Edited 05 Capital!H12 by Olivia Brandt", and any approval over a changed input shows "Changed after sign-off" (e); *given* a stale `expected_version`, *then* 409 `cell_version_conflict` and the grid reloads the cell.
- **AC-4.4** *When* Samuel (reviewer) edits a cell, *then* the change becomes a proposal routed for approval (DEC-84: reviewers propose, preparers edit); an agent never edits a cell directly.
- **AC-4.5** *Given* a formula outside the closed grammar (for example a function name not in SUM, ROUND, IF, MIN, MAX), *then* 422 `formula_invalid` with the code; nothing is ever evaluated with `eval`.
- **AC-4.6** *When* Olivia clicks Open in Excel, *then* `Ridgeline_2025_1065_Workbook_v2.xlsx` downloads with live formulas from the DAG, client strings (account names, memo text) written as text even when they start with "=", and byte-identical output for identical data (P-69, P-19).
- **AC-4.7** *Given* the version picker, *when* Olivia picks "Version 1 · Run 1", *then* the grid shows that version read-only.

### F5 · Allocation structure and the agreement reader (TXP-06)

*As Samuel, I want the allocation structure proposed from the partnership agreement with clause citations, and approved by me at L3.*
- **AC-5.1** *Given* the agreement reader is cleared for the firm and both consents exist, *when* Run 1 reaches `interim_closing_706d`, *then* the reader proposes a straight percentage with a §706(d) interim closing (monthly convention) for the 6/30/2025 transfer, each proposed parameter citing LPA §4.1 or Assignment §3 (`document_text` with bbox), verified before display; instructions inside the agreement are never followed (ADR-052).
- **AC-5.2** *Given* the proposal, *then* TXP-06 c shows Pending approval with the ApprovalCard reasoning and two citations; *when* Samuel clicks Approve structure, *then* SHL-12 opens at Manager L3 (c2); *when* he signs, *then* the structure is Approved, the capital and K-1 groups re-run, and an agent or staff member signing gets 403 `level_not_permitted`.
- **AC-5.3** *Given* the approved structure (a), *then* the bars show two periods of 628,100 with five partner fills and a hatched remainder, partner totals sum to 1,256,200, and Pell Street II LLC receives nothing in period 1; *when* Samuel picks Meera Shah in the rail (a2), *then* her series is outlined in every bar and the tooltip reads "Meera Shah · 238,678 · 38% of 628,100".
- **AC-5.4** *Given* Harborview (b), *then* return of capital 4,000,000 + preferred return 312,000 + catch-up 78,000 + promote 510,000 = 4,900,000, the back-solve plugs 900,000, the GP receives 20%, and the checks foot.
- **AC-5.5** *When* Samuel edits a rung inline (pref 8%, catch-up 20%, promote 20/80) (d), *then* `POST …/allocation-structure/preview` recomputes the right column with no persistence and the back-solve shows Pending; *when* he saves, *then* `PUT …/draft` creates a new draft version that needs an L3 sign-off again.
- **AC-5.6** *Given* agents off, *then* a manager keys the structure, periods and transfer with citation notes, and code computes the same results.

### F6 · Schedule K and K-1 drafts (TXP-05, sheet 09)

*As Samuel, I want Schedule K to equal the sum of the K-1s, line by line, with every amount traceable.*
- **AC-6.1** *Given* the approved structure, *then* TXP-05 a shows K = Σ K-1 on every line (1,231,600 · 18,400 · 6,200 · 600,000) with Items J (beginning and ending percentages), K (11,048,300 split by profit percentage) and L (ending capital), and the Analysis of Net Income excluding tax-exempt income; every row crossfoots (Pell Street Ventures box 2 = 400,270).
- **AC-6.2** *When* Samuel opens line 2 (a2), *then* the Form 8825 popover shows the three properties behind 1,231,600; *when* he opens 18a (a3), *then* SHL-09 shows `06 Schedule K!C31` after TJE-1.
- **AC-6.3** *Given* the M-2 issue is open, *then* Item L shows "off 6,200" (a4) linking to TXP-07 and TXP-10; after the fix (c), Item L ties at 6,866,200.
- **AC-6.4** *When* Samuel opens a partner header (a5), *then* the menu offers that recipient's K-1 package on TXP-12 (T-02) and the TAX-11 K-1 page as a planned link.
- **AC-6.5** *Given* the `federal_k1s` step, *then* each partner's draft K-1 values are written to sheet 09 and upserted into T-02's `k1_packages` as Draft (pre-release) with a reference (DEC-88); *given* any portal principal, including Meera Shah through her own 1040 scope, *then* no draft value is readable (INV-4).
- **AC-6.6** *Given* State K-1 amounts (b), *then* the IL, CO and NY figures come from sheet 08 cells with their import or keyed provenance; T-05 computes no state amounts.

### F7 · Capital accounts, M-2 and section sign-off (TXP-07)

*As Samuel, I want each partner's capital rolled in three bases with the transfer handled correctly and the M-2 tie shown.*
- **AC-7.1** *Given* Run 2, *then* TXP-07 a shows Tax, 704(b) and Book (tax basis) per partner; the Tax column omits tax-exempt interest, so the tally reads "M-2 ties · off 6,200" and five cells are amber; 704(b) equals book with no revaluations or §704(c) items.
- **AC-7.2** *When* Samuel opens the tax-exempt cell for Meera Shah (a2), *then* provenance shows `05 Capital!H9` empty, expected `'06 Schedule K'!C31 × 38%` = 2,356.
- **AC-7.3** *Given* the transfer (a3), *then* 331,405 = 2,319,835 × 5/35 moves at 6/30 in all three columns, Transfers nets to 0, and the transferee succession follows Reg. §1.704-1(b)(2)(iv)(l), including the first-half tax-exempt share.
- **AC-7.4** *When* Samuel clicks Sign off… with the tie-out off (b2), *then* SHL-12 shows the blocked state "1 tie-out is off · resolve it or sign off with a note"; `POST …/sections/capital-accounts/sign-off` without a note answers 409 `tie_out_off`, and with a note it records the sign-off and the audit event `tie_out.off_acknowledged`.
- **AC-7.5** *Given* the fix approved (c), *then* the Tax column shows 6,200 in "Other increases", END TOTAL 6,866,200, the tie passes, and an earlier sign-off computes stale.
- **AC-7.6** *Given* the Computing state (d), *then* tally values fade in 45 ms apart and rows 70 ms apart, and nothing animates under reduced motion; *given* the signed state (e), *then* the header reads "Reviewed · SI".

### F8 · Issues, tie-outs and the fix loop (TXP-10, TXP-11 b and b2)

*As Samuel, I want every blocker in one queue, linked to its cells, with fixes that come back for my approval.*
- **AC-8.1** *Given* any completed run, *then* the `tie_out_check` activity compares M-2 line 9 with Schedule L line 21, the capital tie, Σ K-1 = K and TB footing, and raises or auto-resolves C3 issues deduplicated on `(work_item_id, source_ref)`; *Why this was surfaced* is composed from code facts by a deterministic template (no model text), and `issue_links` point at the cells.
- **AC-8.2** *Given* the queue, *then* sections "Waiting on the client" (5) and "Review points" (6) sum to the badge 11, which is derived and never stored (I-01 R4); search, filters and Show resolved work; selecting a row fades the detail in 200 ms and lights the linked cells in the TXP-11 split.
- **AC-8.3** *Given* the M-2 review point (a), *then* the ApprovalCard shows the agent's reasoning, both changes and the evidence; *when* Samuel approves in SHL-10 (a2) with a matching `seen_hash`, *then* the cells are applied through `record_value`, the checkpoint "M-2 tax-exempt interest" is created, Run 3 starts for the capital and K-1 groups, the issue moves In progress (c, agent monogram spinner, mini run row) and then Resolved when the tie passes (d, 9:52 AM, badge 10); *given* a stale hash, *then* 409 `proposal_changed`; Undo inside 10 seconds writes `proposal.undone` and voids the re-run grant (DEC-24).
- **AC-8.4** *When* Samuel rejects a fix, *then* a reason code is required.
- **AC-8.5** *When* Samuel writes fix instructions in the composer ("Tell the agent how to fix this…", SHL-15), *then* the fix runner (T-04's `issues.fix_runner`, registered here for workbook targets) returns a new proposal in propose mode; it never applies a change itself.
- **AC-8.6** *Given* the §754 issue (b), *when* Samuel chooses Send to client…, *then* a POR-04 request is created in template wording only, the internal note never appears in it, and Owen Calder sees only that request (INV-4); Send reminder uses the C16 template and is sent by a person; the agent can be an assignee but never resolves or approves its own fix.
- **AC-8.7** *When* a person resolves an issue without an applied fix, *then* a note is required.

### F9 · Preparer memo (TXP-01)

*As Samuel, I want a cited memo that tells me where to spend review time, and that goes stale when its figures change.*
- **AC-9.1** *Given* `tax.entity_agents` on and consents in place, *when* Olivia drafts the memo, *then* a run streams the sections (b, skeleton) from code-computed figures only; every figure in the text is a citation or a code fact (number provenance 1.0), and markers [1]–[6] point at verified sources.
- **AC-9.2** *When* Olivia adopts it, *then* an L1 sign-off is recorded ("Adopted by OB · Sep 10"); *when* Samuel approves it in SHL-12 (a3) at 9:40, *then* an L2 sign-off is recorded (c); the preparer can never give the L2 (`not_preparer_of_target`).
- **AC-9.3** *When* Samuel hovers marker 2 (a2), *then* the Partners and Allocation rows and 331,405 light purple across panes within 360 ms; a click opens SHL-07 and then SHL-08.
- **AC-9.4** *Given* the 9:51 fix changes ending capital, *then* the memo's fingerprint over its cited cells differs, the memo reads Stale with "ending capital 6,860,000 → 6,866,200" (d), `tax_memo.went_stale` notifies the preparer and reviewer, and the L2 computes stale; *when* Olivia clicks Regenerate sections, *then* only the affected sections are redrafted and her edited section is kept.
- **AC-9.5** *Given* agents off, *then* Olivia writes each section in place; adoption, approval and staleness work the same.
- **AC-9.6** *Given* the Opportunities section, *then* "Raise with client…" is a planned link (TAX-15 in T-08, PRJ-01 in T-09).

### F10 · Decisions: the §706(d) question and the §754 card

- **AC-10.1** *Given* the `convention_706d` question, *then* its options are computed by code (interim closing calendar-day, semi-monthly or monthly; proration calendar-day only), the recommendation comes from `decisions.recommender` with a cited reason, and only a member holding the step's answer right may answer.
- **AC-10.2** *Given* the §754 decision card kind `section_754` (SHL-11 g), *then* it is reserved to the engagement partner (Daniel Reyes), its options are Elect and Do not elect, its facts come from code (transfer 6/30/2025, price 360,000, transferred tax capital 331,405, §743(b) placeholder 28,595), and the recommendation is cited; *when* Daniel decides with a rationale, *then* the decision is recorded human-only and HOME-02 removes the row; the client-side question still goes to Owen Calder through the TXP-10 b request.

### F11 · Reconciliation to the engine of record and the export section

- **AC-11.1** *Given* an approved checkpoint and final approval, *when* a reviewer exports to CCH Axcess (TAX-09, T-01), *then* the entity section carries the TTB by CCH line code and the partner allocations by Schedule K line from the **approved checkpoint only**; *given* Unmapped > 0, *then* export is refused; no agent can export.
- **AC-11.2** *Given* a CCH import checkpoint is approved, *then* reconciliation compares Schedule K totals, each partner's K-1 boxes, ending capital and M-2 with the workbook; *given* a difference, *then* one `engine_diagnostic` issue per difference blocks final approval; *given* none, *then* the reconciliation reads "0 unexplained differences" and Accrued figures that the engine owns are labelled "Accrued tie-out (shadow)".

### F12 · Final-approval guards

- **AC-12.1** *Given* Unmapped > 0, an unapproved allocation structure, an open issue whose `blocks` includes final approval, an off tie-out without a note, or a run in progress, *when* Daniel opens final approval (TAX-05 → SHL-12 h, T-04), *then* the guard in `tax/approval.py` answers 409 with `blockers[]`, each shown in words; *when* all clear, *then* the L4 approval records; an agent principal is refused.

### F13 · Agent-off, consent and entitlement paths

- **AC-13.1** *Given* `tax.entity_agents` off, or a capability not yet cleared, *then* every model-backed control is disabled with its reason from `GET /v1/agents/capabilities`, never hidden behind an error, and the J08 P0 steps complete by hand.
- **AC-13.2** *Given* a firm whose entitlement `tax.entity_returns` is refused (CPA memos unsigned, non-synthetic firm), *then* the return opens the coordination view with a designed locked state, and no workbook route answers.
- **AC-13.3** *Given* `tax.entity_workspace` off, *then* nothing in the entity layout is reachable and no pane renders blank.

### F14 · Seed, golden figures and CPA review

- **AC-14.1** *Given* `make seed-demo`, *then* the Ridgeline and Harborview slices load through service APIs (never direct inserts) with the run, memo and issue timeline in §1 and the named snapshots Sep 8 10:02 AM, Sep 10 4:12 PM, Sep 14 9:24 AM and 9:52 AM.
- **AC-14.2** *Given* the golden suites, *then* every figure in §1 is an exact-`Decimal` case transcribed by N from blueprint §9.8 and the specs, the Schedule L conflict is encoded as DF-34 decided, and each case's `reviewed_by` references a signed memo `docs/quality/golden-reviews/tax_entity.<engine>@<version>.md` *(new)* before M18.
