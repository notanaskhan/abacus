---
id: SPEC-649
title: T-04 return review workspace and individual returns (TAX-04 to TAX-08, TXI-01 to TXI-03)
status: draft
owner: ayushkbhatia
risk_zone: green
created: 2026-11-09
updated: 2026-11-09
epic: T-04
task: T-04-T02 (TASK-6317)
adrs: [ADR-231, ADR-167, ADR-160, ADR-161, ADR-166, ADR-321, ADR-233, ADR-234, ADR-230]
---

# SPEC-649 · Return review workspace and individual returns

The acceptance criteria are the epic's (`docs/plan/epics/T-04.md` §3), numbered as there and adopted here verbatim as the spec of record; this file lists them by story, adds the contract scope (RW-1, WS-1) and the gates (T-04-T01's minutes). Where this file and the epic differ, the epic's later revision wins and this file is corrected.

## Scope
- Screens: TAX-04, TAX-05, TAX-06, TAX-07, TAX-08 (a to f; g and h deferred to W-03), TXI-01, TXI-02, TXI-03: 50 artboards in scope (`docs/screens/<ID>.md`).
- Contracts: RW-1 `docs/contracts/tax-review-workspace.md` and WS-1 `docs/contracts/tax-worksheets.md` (T-04-T05).
- Flags: `tax.review_workspace`, `tax.individual_workpapers` (T-04-T09).
- Gates: `docs/plan/status/T-04-gate-S32.md` (ADR-233 and ADR-234 acceptance open for the agent rows).

## Acceptance criteria
### 3.1 Document tie-out in the Prepare preset (TAX-04 a–e)
- **AC-1.1** *Given* the Feld return at Wed Aug 26, 10:15 AM with 36 documents and Kevin holding the `preparer` function, *when* he opens `/tax-returns/$returnId/review/documents?preset=prepare`, *then* the tree groups documents by category › sub-head with "Review 36" in the tab, the Halvard 1099 loads in the viewer and the "Interest" and "Dividends" leadsheet cards on the sheets pane, and boxes 1a 14,820 and 1b 11,960 light lines 3b and 3a in the demo order (TAX-04a). Under reduced motion the end state appears at once.
- **AC-1.2** *When* Kevin clicks a viewer region or a leadsheet row, *then* its partner lights (click pins, Escape clears and refocuses the origin) with the linked-figure tag "Form 1040 · Line 3b 14,820"; the link comes from a verified `document_text` citation with bbox, never from model text (INV-2).
- **AC-1.3** *When* he presses "Approve Document", *then* one `document_approvals` row (level `preparer`, actor Kevin, human-only CHECK) is written at once, the row shows an ink "✓ 1", Review goes 36 → 35, the footer becomes "× Unapprove Document", and the toast reads "Approved Halvard Securities 2025 Consolidated 1099" (TAX-04b). Unapprove writes a **reversing** row; nothing is deleted (ADR-007).
- **AC-1.4** *Given* line 3b's field reads 14,280 while the extracted 1099-DIV box 1a reads 14,820, *then* the code mismatch check marks the line in `#8E2418` with a flag, the approve button is disabled with "Resolve 1 mismatch to approve", and "Issue…" opens SHL-15 prefilled; a forced POST answers `409 mismatch` with `facts.field_key` (TAX-04c).
- **AC-1.5** *When* Kevin selects the Ridgeline K-1, *then* the viewer shows the watermarked draft, box 5 lights "Taxable interest — Ridgeline K-1 box 5 $4,600", box 18A stays unlit and line 2a keeps ⚑ because an open issue cites it; ⚑ opens TAX-06 with that issue selected (TAX-04d).
- **AC-1.6** *Given* the agent principal or a system actor, *when* it attempts `POST …/document-approvals`, *then* the matrix denies it and the DB refuses the row (INV-1).

### 3.2 Detail and manager review (TAX-05 a–f)
- **AC-2.1** *Given* Mon Sep 14, 9:24 AM, 41 documents, 4 approved at manager level, *then* the Review tab reads 37 for Samuel (documents not approved at the viewer's level, from his `manager_reviewer` function), each row ends with Flag (count), Check ("✓ n" in ink when approved at his level) and Info micro-pills, and the draft K-1 sits beside the Sch E – K-1 matrix with the 2024 column (TAX-05a).
- **AC-2.2** *When* he approves "Ridgeline K-1 Statement A — §199A", *then* Review becomes 36 and the toast reads "Approved for manager review · Samuel Ito" (TAX-05b); Kevin, viewing the same return, still sees his preparer-level count.
- **AC-2.3** The matrix foots to the K-1: 307,900 / 4,600 / 1,550 / 150,000; Item L 1,500,000 + 250,000 + 312,500 − 150,000 = 1,912,500; UBIA 3,938,000 = 25% × 15,752,000; the 2024 column foots to 1,500,000. Totals come from the server (code computes; the table never sums).
- **AC-2.4** *When* he opens ⓘ on a matrix row, *then* SHL-09 shows "Updated Aug 25 by Accrued Agent, from Box 5 of the draft K-1" with ✓ KO · ✓ OB (P-04 provenance over `field_value_versions`).
- **AC-2.5** *When* the Worksheets SheetTab is chosen, *then* the sheets pane shows TXI-01 rows for "Sch E p2 — Ridgeline" (TSJ T) with ✓ KO and ✓ OB (TAX-05d).
- **AC-2.6** *Given* all 41 approved at manager level, *then* a green-tint banner reads "All 41 documents approved at manager level · Samuel Ito" and "Request final approval…" opens SHL-12 h (level Partner, assignee Daniel Reyes); *while* the Draft K-1 chip exists the control is disabled with its tooltip, and `POST /v1/tax/returns/{id}/final-approval-requests` answers `409 {blockers:["draft_k1"]}` (TAX-05e). The request projects a `final_approval` human gate for Daniel (C13, HOME-02); the approval itself stays T-01/T-02's `tax_return.approve` under BH-TAX-02.

### 3.3 Worksheets and field-level sign-off (TXI-01 a–g)
- **AC-3.1** *Given* 9:40 AM, *then* the tree shows Federal and States groups with TSJ tags, a green "+" on agent-created worksheets new this year and an amber pencil on worksheets edited since the last checkpoint; IT-201 "resident + NYC [J]" is selected, its footer says IT-203 is not used and why; line 20 is lit against Box 18A on page 3 of the K-1 (TXI-01a).
- **AC-3.2** IT-201 ties: 598,030 + 1,550 + 16,025 = 615,605; 615,605 − 16,050 = 599,555; 29,791 + 23,014 = 52,805; 17,400 + 9,390 + 20,000 + 4,746 = 51,536; balance due 1,269. Derived lines (33 = 19 + 20 + 22; 37 = 33 − 34; owed) are recomputed in code on every input change; NY tax (line 39) and NYC resident tax (line 47a, 23,014) are `engine_import` values labelled "from CCH Axcess" (DEC-77).
- **AC-3.3** *When* Samuel opens ⓘ on line 20, *then* SHL-09 shows Updated "Sep 14, 9:31 AM", amber "1,550" with struck "0", "Set by Samuel Ito — approved Accrued Agent proposal (checkpoint 'K-1 box 18A')", the reference "Ridgeline K-1 statement p. 3 · Box 18A", Previous "0 · Initial draft · Aug 25" and "✓ SI" (TXI-01b; INV-5).
- **AC-3.4** *When* he edits a field, *then* a reason is required; the save goes through `PUT /v1/fields/return_worksheet/{wid}/{field_key}/value` with `seen_seq`, writes one `field_value_versions` row, creates a checkpoint with cause `human_edit`, recomputes derived lines, and makes any sign-off covering the section stale ("Changed after sign-off"); a stale `seen_seq` answers 409.
- **AC-3.5** *When* he signs off "Payments and credits" through SHL-12 (level L3), *then* every row in the section shows "✓ SI" and the band reads "Signed off · SI 9:52 AM" (TXI-01f); Kevin, who prepared it, cannot sign L2/L3 on it (R-SO-3, `not_preparer_of_target`).
- **AC-3.6** ⚑ on "New York City resident" opens TAX-06 with the residency review point (TXI-01d); the IT-653 row carries "New this year — Ridgeline elected New York PTET for 2025" citing the PTET statement (TXI-01e).
- **AC-3.7** *Given* a residency change to part-year NYC (TXI-03), *then* IT-360.1 appears with a green "+", the NYC rows turn amber "Recomputed by CCH Axcess after import" once the import checkpoint is approved, and the sync chip reads "Out of sync" until the next export (TXI-01g).
- **AC-3.8** The W-2 worksheet shows boxes 1–19 for Mercer Hill Health (wages 268,400 · withheld 52,860 · … · NYC tax 9,390), all ✓ KO · ✓ OB, with box 1 lit on the W-2 (TXI-01c).

### 3.4 Issues (TAX-06 a–g)
- **AC-4.1** *Given* Sep 14, 9:24 AM, *then* the queue groups issues by category path, shows 4 open (2 Missing information, 1 Action required, 1 Review point), and selecting the box 18A issue lights the K-1 region, both ghost values (Form 1040 line 2a 1,550; IT-201 line 20 1,550) and the file chip — nothing else (TAX-06a).
- **AC-4.2** *Given* the Draft K-1 issue (kind Action required, assignee Samuel, priority High, created by Accrued Agent), *then* "What it blocks" names final approval under BH-TAX-02 (Daniel Reyes) and export, "Mark as Resolved" is disabled with "Resolves when the final K-1 is released", `POST /v1/issues/{id}/resolve` answers `409 system_resolved_only`, and the `k1_package.released` consumer resolves it as **system** with a note (TAX-06b).
- **AC-4.3** *When* Kevin presses "Set Fix Instructions", *then* SHL-15 opens with the suggested instruction; *when* he saves "Add 1,550 to line 2a and IT-201 line 20" with Accrued Agent as assignee, *then* the issue goes In progress, the row shows a spinner and "Adding 1,550 to Form 1040 line 2a · Running" (TAX-06e), and the run produces **one proposal with two cited rows**; the agent cannot resolve the issue (ISSUE-001).
- **AC-4.4** *When* Kevin accepts a ghost value, *then* SHL-10 opens with the two-field diff; on approval a checkpoint is created and Issues go 4 → 3; "Reject" asks for a reason code.
- **AC-4.5** *When* he presses "Explain…", *then* an Explain block appears under the body with verified citations only (K-1 box 18A, K-1 statement p.3, IT-201 instructions line 20); numbers in it come from code facts (number provenance 1.0).
- **AC-4.6** *Given* the estimated-payments issue (Waiting on client), *then* the footer shows "Requested Sep 1 · Claire Feld is uploading 2 files now" (TAX-06c); "Ask the client…" on a new issue opens the POR-04 preview, and only a person sends through `issue.send_to_client` (DEC-74; INV-4: the internal note never reaches the portal).
- **AC-4.7** "Mark as Resolved" requires a note; the Resolved filter shows the three Aug 27–28 rows in ink-2 with green-tint "Resolved" (TAX-06f); an empty queue reads "No open issues." (TAX-06g). CSV export needs `export.create` with fresh MFA and escapes formula-leading cells.

### 3.5 Activity and checkpoints (TAX-07 a–f)
- **AC-5.1** *Given* 9:24 AM, *then* Activity lists 24 events newest first with the 76 px right-aligned date column, "{Verb} by {Actor}" titles and ink-2 sub-lines; agent rows read "… by Kevin Osei via Agent" or "by Accrued Agent" only for proposals and self-checks, and **every approval names a person** (INV-5); the Manager review checkpoint is Current and starred (TAX-07a).
- **AC-5.2** *When* the assistant proposes the box 18A fix at 9:29 AM, *then* the Checkpoints chip reads "☰ 1 proposed" and the top checkpoint row "K-1 box 18A · Accrued Agent · 9:29 AM · Proposed · Review" (TAX-07b); Review opens SHL-16 with steps and old → new with causes (b2); after approval at 9:31 AM the chip reads "✓ No changes needed" and Issues 4 → 3 (c).
- **AC-5.3** The kind filter (All · Approvals · Client · Agent · Tax engine · Issues) narrows rows; Agent shows only agent rows (e); a filter with no rows reads "No events match this filter." (e2); search filters live.
- **AC-5.4** *Given* Sep 19, *then* the delivered rows read, newest first, "NY return accepted", "Federal return accepted / Submission ID ••••••2614", "Return transmitted by Daniel Reyes / CCH Axcess e-file", the two 8879 signatures, "Envelope sent by Grace Holloway", "Return exported to tax engine by Samuel Ito / 2025I:FeldJ:V3", "Return approved by Daniel Reyes / Final review complete · BH-TAX-02" (TAX-07d). Engine ids progress V1 (Feb 3) → V2 (Apr 14) → V3 (Sep 10).
- **AC-5.5** A checkpoint row opens SHL-16; Restore… creates a **new** checkpoint and never rewrites history; Compare… diffs two checkpoints in code; star toggles a named checkpoint (TAX-07f).
- **AC-5.6** Activity reads P-05's engagement activity query with a `work_item_id` filter and T-04's ACTIVITY_KINDS; Restricted values are resolved at read time and masked for offshore users (DEC-60); a walled user gets 404 for the route and the return never appears in any list (INV-3).

### 3.6 Assistant (TAX-08 a–f)
- **AC-6.1** *Given* both §7216 consents signed by Jonah and Claire for TY2025 and `tax_agents.enabled` on (synthetic tenant, or a real firm after G-1…G-7), *when* Samuel opens the Assistant chip, *then* the O2 drawer (420, `#F8F8F6`, no scrim, peek) opens over TAX-05 with a new thread and three suggested prompts (TAX-08b).
- **AC-6.2** *When* he asks at 9:29 AM, *then* the narration reads "Reading 41 documents, 3 workpapers and the 2024 return…" (c), and the answer arrives as verified `AgentBlocks` citing the draft K-1 Statement A and the 2024 return, with the K-1 card and treatment chips (Passive · Not a PTP · §199A eligible · NII · States · PTET credits); hovering a K-1 card row lights the box in the viewer underneath (a).
- **AC-6.3** The ApprovalCard shows Reasoning, the diff (Form 1040 line 2a 0 → 1,550; IT-201 line 20 0 → 1,550; NY AGI 614,055 → 615,605), the source row "2025 Schedule K-1 (Draft) · 2 citations" and the policy note "No change to federal tax · reviewer approval required" (a2). QBI ties: 20% × 307,900 = 61,580 < 2.5% × 3,938,000 = 98,450; all figures are code facts (number provenance 1.0).
- **AC-6.4** *When* he presses "✓ Approve adjustments", *then* `POST /v1/proposals/{id}/approve` writes the decision at once, a checkpoint "K-1 box 18A" is created, the linked TAX-06 issue resolves **by Samuel**, the card collapses to "✓ Approved by Samuel Ito · 9:31 AM · checkpoint 'K-1 box 18A'" with Undo for 10 s, and Issues go 4 → 3 (d). Undo inside 10 s writes `proposal.undone` and a restore checkpoint (DEC-24); after 10 s Undo is gone.
- **AC-6.5** "Reject…" requires a reason and shows "Rejected by Samuel Ito · reason: wait for the final K-1" (e); "Edit…" approves with edits and a citation note.
- **AC-6.6** A follow-up "Explain the 2025 vs 2024 change in total tax" returns a block with an inline table (Total tax 110,826 / 123,223; Tax 99,381 / 110,531; Other taxes 11,445 / 12,692) built from engine-imported lines and code deltas only (f; DEC-77, open question Q6).
- **AC-6.7** No assistant output contains "I approved", "I changed" or a reserved verb in the first person (banned-phrase grader 0; L1 lint); drafts of client messages stay drafts.
- **AC-6.8** *Given* one spouse has not signed the AI-disclosure consent, *then* the drawer shows "Agents are off for this taxpayer — §7216 consent isn't on file" with "Request consent…" for permitted roles, and **no model call is made** (C19 tool refusal plus boundary reason `consent_7216`; DF-04).

### 3.7 K-1 treatments (TXI-02 a–e)
- **AC-7.1** *Given* 10:20 AM, *then* the Ridgeline card shows "Schedule K-1 (Form 1065) · Jonah Feld · 25%", the chip cloud, and 8 treatments with Resolved, Rationale, 2024 (SALY) and Status; 7 are Proposed in one ApprovalCard ("Approve 7 treatments") and treatment 8 shows "Approved · SI 9:31" (TXI-02a).
- **AC-7.2** Every figure is a code fact: 141,634 + 96,989 + 69,277 = 307,900 (largest remainder); 7,011 + 4,268 + 4,746 = 16,025; 61,580 = 20% × 307,900 < 98,450; outside basis 1,912,500 + 2,762,075 = 4,674,575. The only amber "Changed vs 2024" row is PTET, with its stated reason (c).
- **AC-7.3** *When* Samuel approves through SHL-10 (`proposal.approve` plus the applier's `k1_treatment.approve`), *then* every row reads "Approved · SI" and the card collapses to "✓ Approved by Samuel Ito · 10:24 AM · checkpoint 'K-1 treatments'" (b). Kevin (preparer) cannot approve (403 `level_not_permitted`).
- **AC-7.4** *When* he edits treatment 1 to Nonpassive, *then* a reason is required (422 `reason_required` otherwise) and the row shows "Overridden · SI" with the reason in ink-2 (d).
- **AC-7.5** *Given* Ridgeline releases its final K-1 on Sep 15, *then* the header turns "Released Sep 15", the consumer diffs draft and final, and the banner reads "Final K-1 matches the draft on every treated box; Item L 1,914,050; outside basis 4,676,125" (e). Because basis changed, approved treatment 5 goes stale and a re-proposal is raised for Samuel; it is **never** silently edited (DEC-84).
- **AC-7.6** The activity's link to the source package is visible only to users who can read both engagements; a wall on either side hides it (DEC-88; INV-3). Draft K-1 values never reach a portal principal (INV-4).

### 3.8 Residency and state allocation (TXI-03 a–e)
- **AC-8.1** *Given* 10:40 AM, *then* facts show with citation chips (co-op statement, deed, organizer answers Sep 9, W-2 box 20, voter record, licenses, 1099 address block → SHL-08 with the region lit), the tally pill reads amber "Review point", and the ask card lists the three code-defined options with the agent's "Recommended" tag (a).
- **AC-8.2** The allocation foots: 268,400 + 6,910 + 14,820 + 307,900 = 598,030; + 1,550 + 16,025 = 615,605; IL/CO/NY sourcing 141,634 + 96,989 + 69,277 = 307,900; PTET credits 7,011 + 4,268 + 4,746 = 16,025 (entity 28,044 + 17,070 + 18,982 = 64,096); IT-112-R = min(11,279, 15,920) = 11,279; NYC gets no other-state credit; IT-225 add-backs 4,746 + 11,279 = 16,025. No "$" in the tables.
- **AC-8.3** *When* Samuel confirms "Full-year New York State and New York City", *then* an SHL-10 proposal is approved by him (`residency.confirm` checked by the applier), a checkpoint is created, the review point resolves (Issues 3 → 2), and the banner reads "Residency confirmed by Samuel Ito · Sep 15, 4:55 PM" (b). The agent principal cannot confirm (INV-1).
- **AC-8.4** *Given* the conflict variant (150 NYC days, Rhinebeck as main home), *then* code rules set Action required with a red-tint banner, option 2 (part-year NYC, IT-360.1) becomes Recommended and "Ask the client…" primary (c).
- **AC-8.5** *When* Samuel opens "Ask the client…", *then* the sheet previews the POR-04 question to Claire Feld with options Brooklyn / Rhinebeck / Both and a Send button only for him (d). On a real firm the wording comes from the firm's question template (DB content); the agent's draft wording appears only on synthetic tenants (DEC-79, ADR-111). Sending creates a request item through `requests.api`; Claire sees only her question (INV-4).
- **AC-8.6** *When* residency changes to part-year NYC, *then* `residency_determination.confirmed` adds the IT-360.1 worksheet, flags "engine re-import needed", and TXI-01 g follows (AC-3.7).
- **AC-8.7** "Sourcing by property…" shows a skeleton with a 12 px spinner while the agent run gathers facts (e); "Open in Excel" downloads a deterministic xlsx (`export.create`).

### 3.9 Return Drafter and box extraction (J06 step 6)
- **AC-9.1** *Given* `extracted_fields` recorded by P-11 for the W-2, 1099s, 1098 and the K-1, *when* a draft run starts (binder complete, document approvals, or "Run draft" on TAX-02 after the Apr 27 train), *then* the deterministic mapper places each box onto its `field_key` with a `document_text` citation (page, bbox, value), and the agent proposes the worksheet set (IT-201, W-2, Sch E p2 — Ridgeline, IT-653 with a "New this year" note), TSJ and judgments only.
- **AC-9.2** *Then* the run raises self-check issues in the demo grammar ("Source K-1 box 18A 'Tax-exempt interest' is not on the worksheet") and creates the **Proposed** checkpoint "Initial draft"; **nothing changes** until Kevin approves it in SHL-16 (INV-1).
- **AC-9.3** *Given* a missing consent, *then* the run goes `waiting_on_inputs` with "§7216 AI consent — Feld (1 of 2 signed)"; the deterministic mapping still runs (no model call) and its proposal can be approved without the agent.

### 3.10 Engine exchange for worksheet fields
- **AC-10.1** *When* Samuel exports after Daniel's final approval (TAX-09, T-01), *then* the W2 workbook carries the `engine_field_key` values of the **current approved checkpoint** only; citations stay in Accrued; no agent can export (DEC-49).
- **AC-10.2** *When* an engine export comes back, *then* engine-computed lines (NY tax, NYC tax, IT-360.1 recompute) land as `engine_import` versions inside an import checkpoint in "Import pending approval", and no value changes until a person approves it (P-18).
- **AC-10.3** *Given* a difference between an Accrued workpaper figure and the engine (e.g. NYC tax 23,014 vs 23,015), *then* one `engine_diagnostic` issue is raised, deduplicated by `(work_item_id, source_ref)`.
- **AC-10.4** Never-transmit tests stay green: no MeF, no ERO role, no transmission from Accrued (requirement R-04).

### 3.11 Consent, boundary and agents-off (cross-cutting)
- **AC-11.1** Every `tax.*` tool that declares `data_class="tri"` refuses before data is fetched when the taxpayer lacks both `use` and `ai_disclosure` consents for the tax year (joint returns: both spouses); the gateway refuses again on `consent_7216` (defence in depth). The refusal is audited and never retried (ADR-115).
- **AC-11.2** On a real firm, a model capability runs only when G-1…G-7 hold for that capability, firm and taxpayer; otherwise `GET /v1/agents/capabilities` drives the DF-04 state and no control is offered that would be refused.
- **AC-11.3** The agents-off J06 passes end to end with `tax_agents.enabled` off: documents, worksheets, issues, checkpoints, sign-offs and final approval all work without a model.
- **AC-11.4** No tool output, citation quote or model context contains a full TIN; offshore users see masked values and cannot reveal (P-12).

### 3.12 Walls, portal scope and attribution (cross-cutting)
- **AC-12.1** A user walled from the Feld engagement gets 404 on every workspace route and sees no count, issue, activity row or assistant thread for it (INV-3, ADR-026).
- **AC-12.2** No workspace endpoint is reachable by a portal principal; Claire sees only request items sent to her; draft K-1s never reach POR-13 (INV-4, DEC-88).
- **AC-12.3** Every decision row (document approval, sign-off, proposal decision, residency confirmation, treatment override, final-approval request) names a human actor; agent work is attributed "via Agent" to its initiator (INV-5).

### 3.13 The freeze window and the live path
- **AC-13.1** From Jan 1 to Apr 20, 2028 every T-04 PR touches **no live-path code**: new files, new routes behind default-off flags, new tables in one expand-only migration run after 8 pm CT, registrations through the per-module `registry.py` (P-39). The live T-02/T-01 tax-pilot paths stay byte-identical.
- **AC-13.2** The live-path edits (TAX-02 "Run draft" wiring, the shared return-frame tab registration, the export field-profile hook in `tax/export.py`) ride the **Thu Apr 27, 2028** train (first after Apr 20), unless T-02/T-03 landed the seams before Dec 24, 2027 (T01 checks).
- **AC-13.3** Flags flip per firm only in a Tuesday 7 pm CT window with the journey e2e passing on staging, a shadow run, a written rollback and both founders' approval (Tue Mar 28 shadow flip; Tue May 2 release flip).

## Invariants
INV-1 (agents propose, people decide: human-only approvals and sign-offs), INV-2 (verified citations, no free numbers), INV-3 (walls answer 404), INV-4 (portal scope), INV-5 ("<person> via Agent"), DEC-77 (the engine computes tax; Accrued computes workpaper figures in code), §7216 (`consent_7216`, no full TIN to a model).
