---
id: SPEC-640
title: A-05 EBP plan audits — plan profile, provisions, census, eligibility, contributions, investments, Form 5500, participants, expenses, estimates and related parties
status: draft
owner: ayushkbhatia
risk_zone: amber
related_adrs: [ADR-004, ADR-005, ADR-031, ADR-050, ADR-052, ADR-064, ADR-089, ADR-112, ADR-400]
related_specs: [SPEC-580, SPEC-620]
created: 2026-11-01
updated: 2026-11-01
---

> **Instructions for coding agents**
> - This is A-05's own SPEC (A-05-T01). Every A-05 row cites it; the Given/When/Then text of each
>   AC is A-05 §3 (`docs/plan/epics/A-05.md`, F1–F13), and the IDs below map one to one onto it.
> - Contract: `docs/contracts/ebp-workpapers.md` (A-05-T04 stub). Screen contracts:
>   `docs/screens/EBP-01.md` to `EBP-09.md` and `AUD-27.md` (51 artboards).
> - Code computes every figure (ADR-050, `assurance/compute/ebp/`); the agent proposes and people
>   verify, adopt, record corrections, evaluate the certification and conclude (ADR-005, INV-1).

## 1. Summary
The employee benefit plan audit for a defined contribution plan (Brightwater Hale's Northwind
Robotics 401(k) Plan, PY2025, a §103(a)(3)(C) audit): the plan profile and its service providers,
the plan provisions read from the adoption agreement, amendments and SPD, the census imported with
SSNs and dates of birth sealed and revealed only by a logged act, eligibility testing on the shared
attribute grid, contributions with remittance timeliness and the one late remittance, investments
with the certification and the trust tie-out, distributions and participant loans, participant
accounts, administrative expenses and operational compliance, the Form 5500 tie-out with its
supplemental schedules, and the estimates, related parties and parties in interest workpaper.

## 2. Problem and context
A-04 delivers planning, the workpaper cell store, materiality and the risk register; A-03 delivers
sampling and the TB mapping. EBP audits need their own figures and checks on top: Schedule H, the
late-deposit rule for a large plan (established practice, never the small-plan safe harbor), the
certification's limits under 29 CFR 2520.103-8 and the parties-in-interest view of a late deposit.

## 3. Actors
Marcus Delaney (senior; EBP-01, EBP-08, EBP-09, AUD-27 c), Hannah Leclerc (manager; EBP-02, EBP-04
to EBP-07, sign-offs), Ana Cruz (staff; EBP-03, EBP-06), Margaret Okonkwo (EP; L4 and the
conclusions reserved to her), Simone Baptiste (AUD-27 on Granite Peak), the Accrued Agent (drafts
only, through A-04's `workpapers.section_drafter` modes), Summit Plan Administrators and the
recordkeeper (third parties through POR-14 request links).

## 4. Scope and non-goals
In: F1–F13 of A-05 §3. Non-goals: defined benefit and health and welfare plans, the Form 5500
filing itself (the TPA files; Accrued ties out), PHI on a non-synthetic firm (`phi_not_permitted`).

## 5. Acceptance criteria
`AC-F1.*` to `AC-F13.*` are A-05 §3's bullets in order (F1 plan profile and providers, F2
provisions, F3 census and logged reveal, F4 eligibility, F5 contributions and the late remittance,
F6 investments and certification, F7 distributions and loans, F8 expenses and compliance, F9
participant accounts, F10 Form 5500 and schedules, F11 estimates, related parties and parties in
interest, F12 agent drafts, F13 the agent-off path).

The S23 foundation rows are numbered for their task files:

| AC | Row | Given / when / then |
|---|---|---|
| AC-1 | A-05-T01 | The ten screen contracts (EBP-01..09, AUD-27) carry every artboard state, their deviations and the agent-off path; census PII is masked with a logged reveal (DEC-1857, DEC-1858). |
| AC-2 | A-05-T04 | `ebp-workpapers` v1 stubs answer from fixtures behind `ebp.modules`, `ebp.form5500_tieout` and `assurance.estimates_rp` (off by default); every field is classified, only masked PII leaves; clients hold no EBP action and the agent only reads (DEC-1859). |
| AC-3 | A-05-T05 | The glossary and status vocabulary carry the EBP words; certification, correction and sign-off acts are human-only (DEC-1860). |
| AC-4 | A-05-T06 | Migration `ebp_core` creates the five tables with forced row-level security; checks and conflicts are insert-only and column-granted; a tenant reads only its own rows (DEC-1861). |
| AC-5 | A-05-T07 | The Northwind PY2025 EBP slice loads as Dana Kowalski with its eight documents, and its figures foot to `tests/golden/ebp/northwind_py2025.yaml` (DEC-1862). |

## 6. Decisions
DEC-1857 (screen contracts, deviations, the agent-off path) and DEC-1858 (census PII masking and
logged reveal, under ADR P-12 and C4; no new ADR).
