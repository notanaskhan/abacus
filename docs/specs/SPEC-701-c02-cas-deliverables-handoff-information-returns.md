---
id: SPEC-701
title: C-02 CAS deliverables, close-to-tax hand-off and information returns — CLS-08 FS package, CLS-12 Handoff to tax, CLS-13 1099 / W-9 tracker
status: approved
owner: ayushkbhatia
risk_zone: amber
related_adrs: [ADR-004, ADR-005, ADR-007, ADR-050, ADR-146, ADR-151, ADR-161, ADR-300, ADR-320, ADR-344]
related_specs: [SPEC-655, SPEC-700]
created: 2026-11-17
updated: 2026-11-17
epic: C-02
task: C-02-T07 (TASK-8506)
---

# SPEC-701 · CAS deliverables, hand-off and information returns

> **Instructions for coding agents**
> - The design is `docs/plan/epics/C-02.md` §3 F7 to F9, §4; task rows `docs/plan/epics/C-02.tasks.csv`.
>   US-7.1 to US-9.4 are adopted verbatim; this file numbers their testable cores AC-1 to AC-20.
> - Contract: `docs/contracts/closes-delivery.md` (C-02-T07). Handoffs CLS-08, CLS-12, CLS-13.
> - Figures are locked to the ledger and computed by code (ADR-050); commentary is the firm's
>   template filled by code, never model prose in a client deliverable (ADR P-25 off, DEC-79).
> - **Never transmit** (R-04, IRIS-001): the IRIS file is exported for a person to upload.
> - TINs only masked; a reveal is a logged action (P-03); TIN never in a log or payload.

## 1. Summary
The close's financial-statement package is built by code from the posted ledger, reviewed and
released to the client portal by a partner, approved by the client and then locked. A locked
December close hands its trial balance to the client's tax return through C12. A 1099 / W-9
tracker prepares information returns from vendor payments, collects W-9s through the portal and
records the filing a person makes in IRIS.

## 2. Gate check (main aceddcbbf, 2026-11-17)
SPEC-700 §2 (ADR-344 accepted; W1 dark). P-19 (ADR-320, deterministic documents; C11), P-62
(ADR-300, reference data: 1099 thresholds and due dates as DB rows), P-18 (ADR-151, never
transmit), P-12 (ADR-167, TIN sealing) accepted. C12 v1 is T-06-T05 (S49). C18 kind
`close_package` is R-02's (consumer request filed in SPEC-700 §3).

## 3. Open questions (epic §11.2)
- **Q3** The reviewer's sign-off on the package, taken inside the release dialog, moves the close to Approved immediately before Delivered.
- **Q6** CLS-08's "Entries posted" precondition accepts posted or `recorded_externally`.
- **Q7** CLS-13 lives at `/closes/1099?client=&year=` (alias `/closes/$closeId/1099`).
- **Q8** Recipient copies are out of scope; the IRIS CSV template version is stored on the batch.
- **Q9** TIN Matching results are recorded manually with evidence.
- **Q10** Commentary is template-first; model drafting only under P-25 per firm, off.
- **Q12** The vendor screen needs no §7216 consent (information returns are not chapter 1 returns); TINs stay masked.
- **Q14** Seven-year firm default for deliverables; W-9 and backup-withholding records at least four years.

## 4. Acceptance criteria
- **AC-1** Assembly is a deterministic DET run that renders three skeleton papers until done (US-7.1).
- **AC-2** The balance sheet and income statement foot (549,195.45; 27,795 and July 31,455) and every figure cites the posted account (US-7.1).
- **AC-3** Only commentary is editable; regenerate keeps commentary edits (US-7.1).
- **AC-4** The SSARS route is decided by rule: AR-C 70 preparation with "No assurance is provided."; CAS by-product after Dec 15, 2026; standalone otherwise (US-7.2).
- **AC-5** Release is refused 409 `release_preconditions_unmet` with the three blockers; only a partner, live and with fresh MFA, releases (US-7.3).
- **AC-6** Release runs in one sequence: re-check, sign-off to Approved, final render, C10 publish, C18 item, POR-20 email, Delivered (US-7.3).
- **AC-7** Client approval shows "Approved by client"; lock needs it (409 `client_approval_required`); reopen records a reason and marks the hand-off for supersession (US-7.4).
- **AC-8** The hand-off is unavailable before a locked December close (`handoff_not_available`) (US-8.1).
- **AC-9** Hand off publishes the snapshot through C12 with provenance, creates the tax issues and notifies the preparer and reviewer (US-8.1).
- **AC-10** A reopen then re-hand-off supersedes v1 and notifies the tax team (US-8.1).
- **AC-11** No TJE ever enters a posting batch (US-8.1; TJE-001, the 0950 CHECK).
- **AC-12** CLS-13 tiles and rule text come from C21 rows; no threshold or date is a code constant (US-9.1).
- **AC-13** Reportability by code marks exactly the six reportable vendors and excludes card payments (US-9.1).
- **AC-14** TINs render masked everywhere; Reveal is logged and refused offshore (US-9.1).
- **AC-15** W-9 requests go through C5 to the client, sent by a person; the vendor-link channel is unavailable (US-9.2).
- **AC-16** TIN-mismatch guidance and backup withholding need manager+, a reason and evidence (US-9.3).
- **AC-17** The 1099 batch approves only after the December close locks (US-9.4).
- **AC-18** Export is a deterministic IRIS CSV; filing and acceptance are manual records with evidence (US-9.4).
- **AC-19** No IRS host, TCC or transmit route exists (US-9.4; IRIS-001).
- **AC-20** Empty and prior-year states read as designed (CLS-13e, f) (US-9.4).

## 5. Task map
T07 stub (this) · T16 migration closes_delivery (S50) · T21 package compute · T23 release · T28
CLS-08 · T29 client approval · T33 W-9 · T38 migration information returns · T39 hand-off · T45
reportability · T46 IRIS export · T47 CLS-13.
