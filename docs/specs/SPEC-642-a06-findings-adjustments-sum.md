---
id: SPEC-642
title: A-06 findings, adjustments and SUM (the N block) — findings rooted on issues, deficiencies, misstatements, proposed entries, approval batches, SUM snapshots and consultations
status: draft
owner: ayushkbhatia
risk_zone: red
related_adrs: [ADR-004, ADR-005, ADR-007, ADR-040, ADR-050, ADR-111, ADR-160]
related_specs: [SPEC-043, SPEC-620, SPEC-640]
created: 2026-11-01
updated: 2026-11-01
---

> **Instructions for coding agents**
> - This is A-06's own SPEC (A-06-T01), written from chapter 03 §3.8, DEC-83, DF-28, DEC-53 and
>   DEC-69. The Given/When/Then text of each AC is A-06 §3 (`docs/plan/epics/A-06.md`, F1–F9);
>   the IDs below map onto it.
> - Contracts: C8 (adjustments; `docs/contracts/adjustments.md`, A-06-T05) and the completion
>   contract (findings, misstatements, sign-off matrix; A-06-T05). C3 (review grammar) and C9
>   (ledger layers) are consumed unchanged.
> - Code computes every figure (ADR-050): projections, SUM under rollover and iron curtain, the CT
>   and PM positions, the adjusted TB. People decide: severity and the SUM conclusion are the
>   engagement partner's cards (C3); approving and sending an entry is a named person's act;
>   nothing is ever posted to a client system (ADR-040, independence).

## 1. Summary
A-06 records what fieldwork found and what the team does about it. A **finding** is a 1:1
extension of a P-04 review **issue** (DEC-83: the issue holds lifecycle, assignee and events; the
finding holds the audit facts). A finding becomes a **deficiency** (control matters, severity
reserved to the EP through a `deficiency_severity` card) or a **misstatement** (factual,
judgmental or projected). A misstatement the client should correct becomes a **proposed entry**
(AJE, RJE, PAJE, TJE, elimination) that a named person approves, batches and sends for the
client's decision through C18; one the client declines may be **passed on SUM** by the EP (DF-28).
The **SUM** (summary of uncorrected misstatements) is computed by code under both views and frozen
as a **snapshot** for the EP's `sum_conclusion` card and A-07's representation letter.

## 2. Problem and context
SPEC-043's `findings` and `misstatements` (0064, fieldwork) are engagement-scoped insert-only rows
for the fieldwork screens. A-06 needs work-item-scoped, versioned records with an issue root, a
severity lifecycle and an adjustment chain, so it adds its own tables under distinct names and
leaves SPEC-043's live tables untouched (DEC-1960; the DEC-1866 rule A-04 used for `risks`).

## 3. Actors
Hannah Leclerc (manager; triages, converts, proposes and sends entries), Margaret Okonkwo (EP;
concludes severity and the SUM, passes misstatements on SUM), Marcus Delaney and Ana Cruz
(preparers), Dana Kowalski (client approver of record, decides entries through C18), the Accrued
Agent (proposes findings with citations through task scope; never decides).

## 4. Scope and non-goals
**In:** schema (T03 adjustments core; T04 completion), status words (T02), C8 and completion stubs
(T05) with consumer tests (T06), the SUM compute library (T07); the services and screens follow
(T09–T30). **Not here:** posting to any client system (dormant by CHECK until an accepted ADR P-16),
the AU-C 265 letter (A-07), the statements' schema (T19, S26), consultations' UI (Q-05).

## 5. Records and states
| Record | States (status vocabulary) | Rules |
|---|---|---|
| `audit_findings` | the issue's lifecycle; route: Under evaluation · Converted to misstatement · Converted to deficiency | one per issue (UNIQUE `issue_id`); ref F-01…; `why_surfaced` sealed, citations verified by C4 before display |
| `deficiencies` | Exception for resolution · Proposed · Concluded · Communicated | Concluded or Communicated needs `severity_concluded` and a human `decision_id` on its card (trigger) |
| `audit_misstatements` | Candidate · Confirmed · Below CT · Proposed to client · Booked · Passed on SUM | refs: AJE-n/RJE-n when booked, PAJE-n when passed (origin kept), BCT-n below CT, PY-n prior year; projection from `sampling.compute` |
| `proposed_entries` | Proposed · Within threshold · Review required · Approved · Rejected · Client approved · Client declined (+ Posted · Failed post · Reversed, dormant) | balanced lines (deferred trigger `unbalanced_entry`); attest client ⇒ Review required (CHECK); lines locked after Approved (`entry_locked`); `pe_posting_dormant` CHECK |
| `proposed_entry_decisions` | approved · rejected · sent_to_client · client_accepted · client_declined · client_question · send_undone | insert-only, human-only bound to the session's actor; `record` channel needs evidence |
| `approval_batches` | — | insert-only, human-only; "Approved by ‹name› under ‹policy vN›" |
| `sum_snapshots` | purpose: conclusion · rep_letter_attachment | insert-only; engine version and inputs hash; the card freezes one |
| `consultations` | open · concluded | concluded only by the consulted person (DEC-83 minimal) |

## 6. Acceptance criteria
- **AC-1 (F1, INV-1):** UPDATE and DELETE on the insert-only tables raise `insufficient_privilege`
  for `abacus_app`; a decision or batch row whose actor differs from the session's is refused.
- **AC-2 (F1):** an unbalanced entry fails at commit (`unbalanced_entry`); setting a posting status
  is refused by `pe_posting_dormant`; an attest client's entry is `review_required`.
- **AC-3 (F1):** the C8 and completion stubs exist in the generated client, answer 501 while their
  flag is off, and the consumer tests are green; C8 v1 is recorded frozen.
- **AC-4 (F1):** the status vocabulary carries every state in §5 with its pill variant.
- **AC-5 (F2, INV-1):** severity is concluded only through the `deficiency_severity` card by the EP
  with a rationale and a fresh second factor; the deficiency's trigger refuses any other path.
- **AC-6 (F4, ADR-050):** for Northwind (252,200 / 189,150 / 12,610) the SUM library returns
  rollover 34,150, iron curtain 22,250, aggregate 34,150 = 18.1% of PM, fill 13.5% with ticks at
  CT 5% and PM 75%; above 50% of PM (the firm standard, default 50%) the result is flagged.
- **AC-7 (F3, ADR-040):** no route, workflow or adapter posts, books or writes an entry to a
  client system; the route-table test fails if one appears.

## 7. Decisions
DEC-1960 (tables beside SPEC-043's), DEC-1961 (status words), DEC-1962 (adjustments core),
DEC-1963 (completion), DEC-1964 (SUM library), DEC-1965 (C8 and completion stubs).
