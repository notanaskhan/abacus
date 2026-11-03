---
id: SPEC-643
title: T-03 TY2027 season readiness — organizer editor, answer effects, extensions and estimates, payments compute and the TY2027 cut-over
status: draft
owner: ayushkbhatia
risk_zone: red
related_adrs: [ADR-005, ADR-007, ADR-027, ADR-050, ADR-089]  # plan decisions P-12, P-18, P-27, P-28, P-62, P-68 in the body
related_specs: [SPEC-401, SPEC-501, SPEC-502]
created: 2026-11-03
updated: 2026-11-03
---

> **Instructions for coding agents**
> - T-03's own SPEC (T-03 kickoff, S26). The Given/When/Then text of each feature is T-03 §3
>   (`docs/plan/epics/T-03.md`, F1–F7); the ACs below are the task acceptance lines of
>   `docs/plan/epics/T-03.tasks.csv`, numbered in task order.
> - Contracts: C5 additive "Questionnaires and answer effects" and the tax schedules API
>   (`docs/contracts/questionnaires.md`, T-03-T02); C21 additive `due_date_rules` payload v2
>   (`docs/contracts/rules-tables.md`, T-03-T04). C1, C2, C13, C16 and C19 are consumed unchanged.
> - Code computes every figure (ADR-050, DEC-77): safe-harbor targets, required annual payments
>   and installments are pure `Decimal` functions with explicit half-up rounding and golden tests.
>   People decide: payment approval is the return's reviewer function; publishing an organizer
>   is its owner's act with fresh MFA; Accrued never transmits a filing (DEC-49).

## 1. Summary
T-03 gets a firm ready for the TY2027 season: staff edit a binder's organizer and its client
wording (BND-03), partners publish organizer templates per tax year, code applies answer effects
(requests, review points, Notices routing), and the tax team runs extensions and estimates on one
ledger (TAX-13) with payments computed by code. TY2027 reference data (due dates, holidays,
tolerances) is database content published by two people (DEC-76); only the engine parameter file
is in the repository.

## 2. Decisions taken at kickoff (2026-11-03)
- §0.1 of the epic is accepted with the plan's defaults: DF-08 (the Payments segment is composed
  from DF-08's union or hidden), DEC-74, DEC-38, DEC-31, DEC-49, DEC-52, DEC-89, DEC-20, DF-31,
  DEC-55, DEC-68 (the freeze windows are calendar notes under AMENDMENT-solo), DEC-85, DEC-43,
  DEC-32, DF-34. Recorded as DEC-2200.
- Upstream contracts exist on main: C5 (`c5-requests-binders.md`, `questionnaires.md`), C21
  (`rules-tables.md`), C1 (`work-items.md`), C19 (`c19-consent-gate.md`). T-01 and T-02 shipped
  their rails (SPEC-501, SPEC-502).
- Matrix names: assurance already owns `estimate.*` (AUD-27 accounting estimates), and the
  glossary keeps the bare word `extension` out of code, so the epic's `extension.*` and
  `estimate.*` rows are `filing_extension.*` and `estimate_schedule.*` (DEC-2200).

## 3. Acceptance criteria
| AC | Task | Criterion |
|---|---|---|
| AC-1 | T01 | Generated tests deny the agent and portal principals every T-03 write and deny payment approval to a user without the reviewer function. |
| AC-2 | T02 | Stubs build both screens in fixture mode while T-02's POR-05 contract tests stay green. |
| AC-3 | T03 | schema_check passes up/down/up, generated tenancy tests pass, and a published template version, an answer, an effect row and an approved payment cannot change. |
| AC-4 | T04 | The payments functions reproduce every TAX-13 figure (110,250; 46,300; 19,990; NY 7,824; 12,733) and the TY2027 installment dates, each output stamped with engine name, version and inputs hash. |
| AC-5 | T05 | Edits save atomically with 412 on a stale version; the preview DTO equals the portal DTO with no internal fields; only the template owner publishes with fresh MFA. |
| AC-6 | T06 | Answers produce exactly one review point and one request each on replay, attributed to the organizer rule and never the agent; a missing notices handler leaves the upload in the binder. |
| AC-7 | T07 | Seed lists foot (79 + 82 = 161; 2 + 1 + 2 = 5); one click approves three payments and sends three confirmation requests attributed to the caller; no route transmits or stores a payment instrument. |
| AC-8 | T08 | An imported ack file moves Feld's 4868 to Accepted and Varga's to Rejected with IND-031-04; no extension transmission path exists. |
| AC-9 | T09–T11, T16 | BND-03 a–e and TAX-13 a–e render in fixture mode with footing counts, no dollar signs in cells, text (not colour alone) for rejects. |
| AC-10 | T12–T14, T17 | Suites fail against a build that leaks `internal_helper`, runs an effect twice, lets a non-owner publish, allows an agent or portal write, or maps an ack to the wrong return. |
| AC-11 | T15, T18 | Seed and fixtures foot to every artboard; TY2027 due dates resolve from published rows carrying both handles; no rule content in a commit except the DEC-76 parameter file. |
| AC-12 | T19 | No T-01 or T-02 flag expires unnoticed; retired flags are gone and entitlement-off still returns 404. |

## 4. Task map
S26: T01 (bundle, red), T02 (contract stubs, amber), T03 (migration, amber), T04 (payments
compute, amber). S27: T05–T09. S28: T10–T17, T19. S29: T18.
