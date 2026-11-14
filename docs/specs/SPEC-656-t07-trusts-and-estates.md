---
id: SPEC-656
title: T-07 Trusts and estates — governing instrument (TXT-01), fiduciary calculation (TXT-02), beneficiaries, K-1s (1041) and the 65-day election (TXT-03), gift and estate workpapers (TXT-04)
status: approved
owner: ayushkbhatia
risk_zone: amber
related_adrs: [ADR-004, ADR-005, ADR-007, ADR-014, ADR-018, ADR-027, ADR-031, ADR-042, ADR-050, ADR-052, ADR-078, ADR-089, ADR-090, ADR-111, ADR-150, ADR-160, ADR-161, ADR-166, ADR-167, ADR-231, ADR-237, ADR-300, ADR-321, ADR-342, ADR-343]
related_specs: [SPEC-401, SPEC-501, SPEC-502, SPEC-651]
created: 2026-11-14
updated: 2026-11-14
epic: T-07
task: T-07-T01 (TASK-8016)
---

# SPEC-656 · Trusts and estates (1041 / 706 / 709)

> **Instructions for coding agents**
> - The design is `docs/plan/epics/T-07.md` §1 to §8; task rows are `docs/plan/epics/T-07.tasks.csv`.
>   The acceptance criteria below are the epic's §3, numbered as there (AC-n.m: story n, criterion
>   m) and adopted as the spec of record; each line here states the testable part. Where the
>   epic and a line here differ, the epic's wording wins and this file is corrected.
> - Screen contracts: `docs/screens/TXT-01.md` to `TXT-04.md` (25 artboards, 6 composed states).
>   Contracts provided: `docs/contracts/fiduciary-workpapers.md` and `estate-workpapers.md`
>   (T-07-T05) and C4 v1.2 `instrument_clause` (T-07-T11, ADR-343).
> - **Code computes, models judge** (ADR-050): DNI, IDD, K-1 (1041) boxes, the 65-day window and
>   every estate figure are `Decimal` outputs of `tax/compute/fiduciary.py` and `estate.py` with
>   `engine_version` and `inputs_hash`. The one capability, `tax.instrument_reader`, proposes
>   determinations with clause citations; a person adopts (L1) and a manager approves (L3).
> - **CCH Axcess stays the engine of record** (ADR-231, DEC-77): Accrued's 706 tentative tax and
>   credit carry "Accrued tie-out (shadow)" until a CCH 706 import exists. Accrued never transmits.

## 1. Summary
A firm reads a trust's governing instrument in a reflowed legal reader beside the trust profile,
records seven determinations each tied to a clause (by hand, or proposed by the Accrued Agent when
the reader is live for the firm and both §7216 consents are signed), adopts them at L1 and
approves them at L3. Code then computes FAI → DNI → IDD → beneficiary allocation → K-1 (1041)
boxes with clause chips on the rows the instrument governs; a changed distribution marks the rows
Changed and stales the L2 sign-off until re-approved (DEC-84). K-1 (1041) packages release only
after final approval and the trustee's Completed 8879-F; each beneficiary sees only their own
K-1. For an estate, the Form 706 workpaper foots six schedules and deductions, computes a shadow
tie-out with DSUE, carries the 2023 gift, the basis to the estate's 1041 and the due dates.
J07 steps 2, 3, 4 and 8 and J19 steps 4–5 become walkable (S47); live at M18.

## 2. Gate check (main 322ca3310, 2026-11-14; DEC-5006)
Checked by P-ID against `docs/adr/backlog.md` and each ADR file's own `status:` (the backlog's
table rows lag the files for P-17, P-18 and P-62; the file wins). F-02 fixes only ADR-116…130
by number; every later number is read from the backlog's "Numbers minted" line.

| P-ID / decision | Subject | On main | State | What T-07 does |
|---|---|---|---|---|
| P-48 (AG-07) | Citation v2, verified before display | ADR-166 | accepted | Clause chips, Cited by, every FAI and estate citation (INV-2) |
| P-48 amendment (T-07-T02) | `instrument_clause`, the eleventh kind | ADR-343 | accepted (#1952, S43) | T05 stub types, T11 verifier, T12 determinations |
| P-12 (DEC-52) | §7216 consents, TRI, sealed TINs, `consent_7216` | ADR-167 | accepted | Reader refusal without both consents; sealed EIN on TXT-01 |
| P-32 (DEC-42) | OCR, Textract, word boxes | ADR-321 | accepted | Scanned page 4, custodial statement, appraisals |
| P-62 (DEC-76) | Reference data split | ADR-300 | accepted (backlog row stale: "to draft") | Due-date rows are DB content; brackets, §642(b), §2001(c), BEA are `parameters/*.yaml` |
| P-68 (DEC-77) | Tax computation boundary | ADR-231 | accepted | TXT-02 is an Accrued workpaper; TXT-04 c carries the shadow label |
| P-69 (DEC-84) | Workbook formula engine, re-approval | ADR-237 | **proposed** (acceptance: Ayush) | Read with its proposed text, as T-05 was built: approved input change → stale + Re-approve; a cross-work-item change raises an Issue |
| P-07 (DEC-36) | Review grammar | ADR-160 | accepted | L1/L3 on the interpretation, L2 on the computation, L4 on estate values |
| P-35 (DEC-28) | Suggestions, proposals, grants, Undo | ADR-161 | accepted | Reader output as suggestions; SHL-10 Approve with edits |
| P-18 (DEC-49) | Tax-engine integration, never transmit | none of its own; ADR-150 (W2 adapter rule) and ADR-231 §6 state it | **not drafted** | Read as DEC-49 and ADR-231 §6 already bind it (as T-01 and T-05 were built): file bridge only, imports land as checkpoints, no transmit path. Nothing assumes more |
| P-26 (DEC-25) | E-signature | ADR-149 superseded by ADR-342 | accepted (ADR-342, DocuSeal) | 8879-F envelope gates release (C7) |
| P-29 (DEC-68) | Busy-season change policy | ADR-151 | proposed (acceptance: Ayush) | Flags expire outside the Sep 1 – Oct 20 window (§5) |
| DF-08 | Undesigned tax states | decided (chapter 09 row) | — | TXT-04 c1 "Approve values" opens SHL-12 at L4 (DV-8); Gifts tab carries 709 history |
| DF-31 | Status vocabulary additions | decided (chapter 09 row) | — | `estate_inventory_item` Valued · Gathering (T-07-T04, DV-9) |

**Red rows open:** P-69 and P-18. The plan's stop rule (chapter 09 §9.1.2) is replaced by the
solo amendment (`docs/plan/AMENDMENT-solo.md` items 2 and 7): T-07 builds on the proposed ADR-237
and on DEC-49 / ADR-231 §6 exactly as T-05 did, records it in DEC-5006, and leaves both
acceptances to Ayush. No T-07 code assumes a P-18 decision beyond the file bridge.

## 3. Open questions (epic §11.2) — the plan's recommended answers (DEC-5006)
OQ-1 eleventh kind (ADR-343, done) · OQ-2 reflowed legal reader built from the clause tree, "View
page image" opens SHL-08 · OQ-3 code-only segmentation with `needs_review` and manual marking ·
OQ-4 `instrument_interpretation` L1 + L3, `fai_dni_computation` L2, `estate_workpaper` L4 (KNW-04
review-level content) · OQ-5 release waits for final approval + Completed 8879-F, not e-file
acceptance · OQ-6 a guardian contact with role `delegate` on the minor's `k1_package` (decided
when T-07-T24 lands) · OQ-7 no standalone 709 screen · OQ-8 "Accrued tie-out (shadow)" until a
CCH 706 import exists · OQ-9 shadow first, live per firm only after the window with ≥ 10
instruments at ≥ 0.95 agreement · OQ-10 Illinois Form 700 shows Pending with a Review point,
never a figure · OQ-11 no wills in the v1 corpus · OQ-12 the fiduciary contact signs §7216
consents for the entity's tax year (counsel confirms; recorded, not assumed elsewhere).
DV-19 (seed contradiction): E0 truth wins — the Calloway 1041 is due Sep 30, 2026 (extended).

## 4. Scope
- Four screens, 25 artboards + 6 composed states: TXT-01 (7 + d1, d2, d3), TXT-02 (6 + f1),
  TXT-03 (6 + a3), TXT-04 (6 + c1). No `revision.md` exists; letters follow the handoff READMEs.
- Modules: `tax` (amber; new `instruments/`, `fiduciary/`, `estate/`, `compute/fiduciary.py`,
  `compute/estate.py`, parameter files); `evidence` (red, T11 only); consumers of `review`,
  `requests`, `signatures`, `organisations`, `practice`, `notifications`, `agents`.
- Flags (T-07-T03, default false): `tax.fiduciary_workpapers`, `tax.fiduciary_k1_release`,
  `tax.estate_workpapers`. The reader is not a flag: its exposure is the AI-policy stage (ADR-186).
- Out of scope (epic §2.3): a standalone 709, Illinois Form 700's interrelated calculation, engine
  figures of record, statement-line and inventory agents, model-drafted text to clients (ADR-111),
  TAX-11, TAX-15, HOME-03 chips, CLI-03, wills, a pricing feed, any transmission.

## 5. Acceptance criteria
Invariants asserted everywhere (F-04 `assertInvariants`): INV-1 the agent never decides; INV-2
every citation shown is verified; INV-3 walls hold (404, no counts); INV-4 portal scopes are
isolated; INV-5 attribution is correct ("‹person› via Agent" for runs, a named human for every
decision). **AC-0** every artboard and composed state maps to one fixture scenario, one endpoint
set and one parity tier in its `docs/screens/TXT-0n.md`, and each screen adds loading, error,
not-allowed (404) and flag-off rows.

### F1 · Attach and read the instrument (TXT-01 d → d2 → a)
- **AC-1.1 (d)** No interpretation: reader without highlights; EmptyState "Instrument not read yet" with Read instrument.
- **AC-1.2** Attaching a client-level file records the evidence version (no bytes copied), the original stays write-once, `instrument.attached` names Kevin.
- **AC-1.3** OCR of scanned page 4 → code segmentation yields Articles I–V with II, III(a), III(b), IV(a), IV(b), V(c) on the right pages, each with regions and a text hash; below the bar → `needs_review` "Clauses need checking", manual marking, no model call.
- **AC-1.4 (d2 → a)** Reader live + both consents: a run starts, d2 shows progress, seven determinations land "Proposed by Accrued Agent" with six clause chips and the footer "Read by Accrued Agent Sep 3 · 7 determinations · 6 clause citations"; every chip verified before display; run attributed "Kevin Osei via Agent".
- **AC-1.5 (d3)** 1 of 2 consents: 409 `consent_required` before any model call; "§7216 AI consent — Calloway Family Trust (1 of 2 signed)"; `instrument.read_refused` audited.
- **AC-1.6 (d1)** Reader off or shadow, or consent declined: Read instrument is not offered and each row shows Record….

### F2 · Trace clauses both ways (TXT-01 a, a2, a3)
- **AC-2.1 (a2)** Hover or focus [IV(a)] scrolls to and lights Art. IV(a) for 360 ms (instant under reduced motion); the row lights purple.
- **AC-2.2 (a3)** Clicking Art. II lists "Fiduciary accounting income"; Escape clears.
- **AC-2.3** A `moved` clause citation shows "Source moved — Re-link…" and disables Approve interpretation until re-linked.
- **AC-2.4** Cited by: "Trust Calculation · Distributable net income 400,000", "Trust Calculation · Beneficiary allocation (Nora 160,000 · Theo 80,000)", "Worksheets · 1041 page 1 · Type of entity: Complex trust ☒", each opening its target lit.

### F3 · Record or edit determinations (TXT-01 a, d1)
- **AC-3.1** A clause-governed key (`trust_type`, `fai_definition`, `trustee_fees`, `principal_invaded`, `grantor_status`) saved without a clause → 422 `uncited_change`; `exemption` and `election_65_day` may be clause-free.
- **AC-3.2 (DV-11)** Editing a Proposed agent row opens SHL-10 "Approve with edits" with a required reason (`set_by_kind='human'`, suggestion `edited`); an adopted or human row opens an O3 sheet with reason and clause picker.
- **AC-3.3** A concurrent second save → 409 `version_conflict` (`expected_version`).
- **AC-3.4** The agent principal holds no `instrument_determination.edit` (generated matrix test).

### F4 · Adopt and approve (TXT-01 a4 → b)
- **AC-4.1** L1 by Kevin adopts the pending suggestions (`adopted_run_id`, R-SO-8); Samuel gets `instrument_interpretation_ready` and a HOME-02 gate `instrument_interpretation_approval`.
- **AC-4.2 (a4 → b)** L3 through SHL-12 with the content hash locks the determinations; header "Approved · Samuel Ito · Sep 14"; button Approved (disabled); `instrument_interpretation.approved` triggers the TXT-02 compute.
- **AC-4.3** Kevin cannot sign L3 after L1 (409 `segregation`, R-SO-3); the agent is refused every sign-off.
- **AC-4.4** A determination changed after L3 (only after a reopen) makes L3 computed stale and blocks recompute until a new L3.

### F5 · Scenario and reopen (TXT-01 c)
- **AC-5.1 (c)** 25,000 to Theo with `source=principal` under IV(b): "Yes — 25,000 (HEMS)", banner "Scenario: 25,000 of principal paid for Theo's tuition under Art. IV(b)", note "Distributions of 265,000 carry out DNI under §661: Nora 160,000 · Theo 105,000 · trust retains 135,000"; figures from the engine.
- **AC-5.2** Reopen with a reason → Reopened, TXT-02 L2 stale, TXT-02 shows f1 until a new L3, `instrument_interpretation.reopened` audited; after a release, an Issue is raised and a superseding package is offered.

### F6 · Compute FAI → DNI → IDD → K-1 boxes (TXT-02 a, b, c)
- **AC-6.1 (a)** Calloway base: FAI 430,000; fees 7,500 to interest and 22,500 to dividends; DNI 400,000 (100,000 / 300,000 / qualified 240,000); IDD = min(240,000, 400,000) = 240,000; Nora 66.7% → 160,000 (40,000 / 120,000 / 96,000); Theo 33.3% → 80,000 (20,000 / 60,000 / 48,000); retained DNI 160,000; exemption (100); taxable income 159,900; note "FAI not distributed: 430,000 − 240,000 = 190,000 added to principal under Art. IV(a)"; tally "Σ K-1s = DEDUCTION" tie.
- **AC-6.2** Clause chips only where the instrument governs: V(c) trustee fees, II capital gains, III(a) distributions, IV(a) undistributed DNI; gains never in DNI without a clause.
- **AC-6.3 (b, c)** Collapse-all shows four top rows; By character: 100,000 · 40,000 · 20,000 · 40,000 | 300,000 · 120,000 · 60,000 · 120,000 | qualified 240,000 · 96,000 · 48,000 · 96,000 | 400,000 · 160,000 · 80,000 · 160,000.
- **AC-6.4** Every computation carries `engine_name`, `engine_version`, `inputs_hash`, `parameter_set`, `computed_at`; same inputs → same hash and output; a new engine version marks dependents `out_of_date` and a person approves the recompute.
- **AC-6.5 (f1)** No approved interpretation: 409 `interpretation_not_approved`; TXT-02 shows f1.

### F7 · Changed and re-approval (TXT-02 d → a2 → e)
- **AC-7.1 (d)** Theo Dec 15 → 100,000 after L2 on v3: v4 distributions 260,000, IDD 260,000, 61.5% / 38.5%, Theo 100,000 (25,000 / 75,000 / 60,000), retained 140,000, taxable 139,900; Changed pills with struck priors; banner "Theo's Dec 15 distribution edited · re-approval needed"; Re-approve…; L2 computed stale.
- **AC-7.2 (a2 → e)** L2 re-approval shows "✓ SI" and "Reviewed · SI"; Changed marks clear.
- **AC-7.3** Released K-1s from v3 → an Issue "Released K-1s differ from the current calculation", never a silent update.

### F8 · Export and engine tie-out
- **AC-8.1** "Open in Excel" is a deterministic XLSX; two exports of one version are byte-identical; the download is audited.
- **AC-8.2** TAX-09 export from an approved checkpoint carries type of entity, income lines, line 18 IDD and K-1 (1041) boxes by `engine_field_key`.
- **AC-8.3** A CCH 1041 import lands as Import pending approval; a difference (line 18 240,001 vs 240,000) raises one `engine_diagnostic` Issue; no path transmits.

### F9 · Allocation and K-1 drafts (TXT-03 e → a)
- **AC-9.1 (e)** No signed computation: "Run the trust calculation to allocate DNI to beneficiaries."
- **AC-9.2 (a)** Nora 160,000 (Jun 30 80,000 · Dec 15 80,000) · 66.7% · 160,000 · 40,000 · 120,000 · 96,000; Theo 80,000 (Dec 15) · 33.3% · 80,000 · 20,000 · 60,000 · 48,000; totals 240,000 · 100.0% · 240,000 · 60,000 · 180,000 · 144,000; TIE-OUT line 18 240,000 tie; DELIVERY "Portal (K-1 recipient) · not a firm 1040 client"; tally 65-DAY ELECTION "Not made", K-1s "Draft · 2".
- **AC-9.3** Packages are "Draft K-1 · pre-release" with boxes from the signed version; no portal principal reads a draft; a beneficiary-1040 hand-off is a reference visible only to users who can read both engagements.

### F10 · Release K-1s (TXT-03 a → a2 → b, a3)
- **AC-10.1 (a)** Without final approval or a Completed 8879-F: Release disabled with Lock and the accessible reason "Requires final approval (Daniel Reyes) and Form 8879-F signed by the trustee"; a direct POST → 409 `gate_unmet {final_approval, form_8879_f}`.
- **AC-10.2 (a2 → b)** With both: each package releases to its own `k1_package` grant; discs olive ✓; "Released Sep 28"; Resend…; the PDFs are CCH's final K-1 (1041) PDFs.
- **AC-10.3** Nora sees only Nora's K-1 and not Theo's package, the trust return or its documents; Eleanor cannot read Nora's or Theo's returns; Theo's package with Nora's session → 404.
- **AC-10.4 (a3)** Drift past Pub 1345 tolerance: 8879-F `superseded_by_change`, step 2 reverts, release relocks, a released package is never silently replaced.
- **AC-10.5** The agent is denied release, resend and supersede.

### F11 · The 65-day election and the trustee question (TXT-03 c, d)
- **AC-11.1** Card: "TY2025 window — Jan 1 – Mar 6, 2026 · closed", "Distributions in window — None", "Decision owner — Eleanor Calloway (trustee)", "TY2026 window — Jan 1 – Mar 6, 2027"; window end from the engine (Mar 6 / Mar 5 leap); paragraph is the firm template with retained DNI 160,000, the $15,650 threshold from the parameter file and 3.8% NIIT.
- **AC-11.2 (c)** Recording the TY2026 decision with the Feb 20, 2027 50,000 payment: "Elected for TY2026 · 50,000 paid Feb 20, 2027"; "Treated as paid on Dec 31, 2026 on the 2026 Form 1041"; human-only (DB CHECK); Eleanor owner, Samuel recorder.
- **AC-11.3 (d)** Ask the trustee: the firm template "Would you like to make additional distributions to Nora or Theo before Mar 6, 2027?"; Send publishes a C5 question with 10-second Undo; the agent drafts and sends nothing.

### F12 · Estate inventory and deductions (TXT-04 a, b)
- **AC-12.1 (a)** A 3,850,000 / 3,790,000 / 3,850,000 Valued; B 8,240,000 / 7,965,000 / 8,240,000 Valued; C 412,000 ×3 Valued; D 1,000,000 / 1,000,000 / — Gathering; F 186,000 ×3 Gathering; I 2,712,000 / 2,640,000 / — Valued; totals 16,400,000 / 15,993,000 / 12,688,000; basis null for IRD and non-probate life insurance by rule.
- **AC-12.2** Each amount carries a `document_text` citation or is Gathering; Gathering opens TAX-03 intake.
- **AC-12.3** Request appraisal… opens SHL-14 prefilled for Paul Thornbury with `linked_ref`; only a person sets Valued.
- **AC-12.4 (b)** 28,500 + 240,000 + 131,500 + 500,000 = 900,000; "§642(g) election: 706 or estate 1041 — pending"; the election is a human choice with a reason.

### F13 · Estate computation and gifts (TXT-04 c, d, f, c1)
- **AC-13.1 (c)** Taxable estate 15,500,000; adjusted taxable gifts 1,200,000; base 16,700,000; tentative tax 6,625,800 (345,800 + 40% × 15,700,000); BEA 15,000,000 + DSUE 3,000,000 = 18,000,000; credit 7,145,800; net tax —; Without DSUE: credit 5,945,800 → 680,000; banner "Form 706 required: gross estate plus adjusted taxable gifts (17,600,000) exceeds the 2026 basic exclusion amount (15,000,000)"; every Accrued figure labelled "Accrued tie-out (shadow)".
- **AC-13.2** `avd_available=false`; the UI never presents AVD as available.
- **AC-13.3** Illinois card: "Required — … · Pending" and a Review point; never a figure.
- **AC-13.4 (d)** 2023 · Paul Thornbury · Cash · 1,217,000 · 17,000 · 1,200,000 · Filed Apr 15, 2024 ✓; 2024–2026 within 18,000 / 19,000 / 19,000; "Adjusted taxable gifts 1,200,000 tie".
- **AC-13.5 (f)** ⓘ on Applicable exclusion opens the derivation popover with "Provenance ›".
- **AC-13.6 (c1)** Approve values… opens SHL-12 at L4 (engagement partner only); agent and non-partners refused; a later value change stales L4.

### F14 · Due dates and extension (TXT-04 e)
- **AC-14.1** Due chip "Due Nov 2, 2026 · 4768 to May 3, 2027" from the practice due-date engine (DOD Feb 2, 2026 + 9 months; +6 months rolled from Sunday under §7503); 8971 is the earlier of 30 days after the due date or after filing.
- **AC-14.2 (e)** A recorded Form 4768: "Extended to May 3, 2027"; the return stays Gathering.

### F15 · Contract, data and vocabulary (S44 rows)
- **AC-15.1 (T03)** The generated matrix test denies the agent principal every edit, approve, reopen, record, release and send action in `tax.yaml`'s T-07 rows; portal principals deny everything but T-02's `k1_package.read_own`.
- **AC-15.2 (T04)** Codegen emits the new status StrEnums and `status.gen.ts` words; the copy lint rejects "Ties" on TXT-02 and TXT-04.
- **AC-15.3 (T05)** Every stub route answers under its one action behind its flag (404 while off); the typed fixtures foot 430,000 − 30,000 = 400,000 and 16,400,000 − 900,000 = 15,500,000; no route returns instrument text (clauses carry labels, pages, regions and hashes only).
- **AC-15.4 (T06)** Consumer tests for C4 `instrument_clause`, C7 `form_8879_f`, C10 1041 release, C17 tax tool shapes, C19 consent on a trust taxpayer and C21 fiduciary rule kinds fail when a provider renames a field T-07 reads.
- **AC-15.5 (T07)** One migration head; RLS isolates two tenants on every new table; the human-only CHECK rejects an agent-recorded election; insert-only tables have no UPDATE grant.
- **AC-15.6 (T08)** Every TXT figure foots in a seed test (430,000; 400,000; 240,000; 60,000 / 180,000 / 144,000; 16,400,000; 15,993,000; 12,688,000; 900,000).

## 6. Task map
S44: T01 this SPEC and the screen contracts · T03 protected bundle (red) · T04 vocabulary (red) ·
T05 stubs and contract docs · T06 consumer tests · T07 `fiduciary_core` · T08 seed slice.
S45: T09 fiduciary engine, T10 goldens (N), T11 clause kind (red, N), T12 instrument service, T13
reader capability (red), T14 tools, T15 TXT-01 FE. S46: T16 computation service, T17 TXT-02 FE,
T18 eval suite, T19 CCH 1041 (red), T20 ADR-078 tests (N), T21 live swap, T22 estate backend.
S47: T23 beneficiaries and election, T24 release gate (red), T25 TXT-03 FE, T26 TXT-04 FE, T27
estate goldens (N), T28 ADR-078 tests of N's red work, T29 rollout, T30 journeys, T31 parity, T32
close-out. Task files for the S44 rows: TASK-8017 (T03) to TASK-8022 (T08).

## 7. Deviations
DV-1 to DV-19 as the epic's §2.5, each recorded in its screen contract.
