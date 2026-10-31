---
id: SPEC-620
title: A-04 Audit planning & risk (G4) — workpaper core, materiality, risk register, fraud, internal control, SOC 1
status: draft
owner: ayushkbhatia
risk_zone: amber
related_adrs: [ADR-004, ADR-005, ADR-031, ADR-042, ADR-050, ADR-052, ADR-056, ADR-064, ADR-089, ADR-160, ADR-161]
related_specs: [SPEC-008, SPEC-300, SPEC-308, SPEC-310, SPEC-313]
created: 2026-10-31
updated: 2026-10-31
---

> **Instructions for coding agents**
> - This is A-04's own SPEC (A-04-T02). Every A-04 row cites it; the Given/When/Then text of each
>   AC is A-04 §3 (`docs/plan/epics/A-04.md`), and the IDs below map one to one onto it.
> - Contracts: `docs/contracts/workpapers-core.md` and `docs/contracts/audit-planning.md`
>   (A-04-T01 stubs). Screen contracts: `docs/screens/AUD-04.md`, `AUD-05.md`, `AUD-07.md`,
>   `AUD-08.md`, `AUD-09.md`, `AUD-10.md`.
> - Code computes every figure (ADR-050); the agent proposes and people decide (ADR-005).

## 1. Summary
The planning half of an audit: one workpaper cell store reused by A-05 and A-08, the program
workpaper and the narrative risk workpaper, materiality and the engagement partner's decision,
the risk register with linkage and the significant-risk approval that satisfies gate G4, the fraud
brainstorm with EP-approved minutes, internal control and its exceptions, and service
organizations with SOC 1 evaluations.

## 2. Problem and context
SPEC-300 (planning v0, fieldwork module) and SPEC-308 (working papers v0) gave the Northwind
journey a first materiality figure, a risk list and cell-addressed papers. They have no versioned
partner decision, no SAS 145 register, no RMM by policy, no linkage, no brainstorm, no internal
control or SOC evaluation and no G4. A-04 adds them behind six flags without renaming any live
SPEC-300 or SPEC-308 route (DEC-1757): those retire when their last consumer moves.

**Supersession of SPEC-008's non-goals.** SPEC-008 §4 listed "Materiality, risk assessment and
procedures beyond request items" as non-goals. This SPEC supersedes that line: materiality,
risk assessment and procedures (instantiated from the pinned methodology version, with tailoring)
are in scope here. SPEC-008's other non-goals stand.

## 3. Actors
| Persona | Role | What they do here |
|---|---|---|
| Margaret Okonkwo | Engagement partner; QM owner | Decides materiality, the register card and reliance; leads the brainstorm; approves the minutes |
| Hannah Leclerc | Manager | Reviews (L2); routes for approval; reminds; tailors procedures |
| Marcus Delaney | Senior | Prepares (L1), adopts suggestions, converts flags, proposes |
| Accrued Agent | — | Drafts suggestions with citations on a person's behalf ("Marcus Delaney via Agent"); never decides |
| Dana Kowalski, Sam Ortiz | Client, third party | Answer questionnaires and upload a bridge letter; see no A-04 table (INV-4) |
| Thomas Whitcombe | EQR | Reads; excluded from the brainstorm |

## 4. Goals and non-goals
**Goals:** A-04 §3.1–§3.8 (US-1.1 … AC8.4).
**Non-goals:** A-04 §2.2: the engagement run (P-10) and run dock (P-09); concluding severity,
misstatements and review notes (A-06); AU-C 260/265 letters (A-07); POR-15 (R-02); EBP workpaper
targets (A-05); component materiality (A-09); Teams transcripts; rates outside the firm range (a
consultation first, Q-05); ICFR (X-07); fund semantics (X-06).

## 5. Acceptance criteria
Each AC is A-04 §3's text verbatim by ID; the owning task writes its test (`test_acN_...`).

| AC | A-04 § | Owner tasks | Summary |
|---|---|---|---|
| AC-1 | AC1.1 | T11, T21 | A `gap` draft writes only suggestions with verified citations |
| AC-2 | AC1.2 | T04, T21 | L1 adoption by a person adopts every pending suggestion (R-SO-8) |
| AC-3 | AC1.3 | T04 | A later edit makes L2 stale; `sign_off.went_stale` |
| AC-4 | AC1.4 | T04, T21 | The SHL-07 stepper; moved sources are not offered as verified |
| AC-5 | AC1.5 | T07, T21 | Linkage and Audit Approach tabs from the records |
| AC-6 | AC1.6 | T04 | 409 `version_conflict`; 422 `reason_required`; writes via `record_value` |
| AC-7 | AC1.7 | T04 | Byte-identical export; client strings as text; audited |
| AC-8 | AC1.8 | T04 | "Waiting on inputs" with request ids |
| AC-9 | AC1.9 | T07 | 67 procedures, 21 mandatory; 409 `mandatory_step` |
| AC-10 | AC1.10 | T16, T30, T36 | Walls 404; client principals and `client_service` 403/404; no portal scope |
| AC-11 | AC2.1–AC2.2 | T11, T27 | `risk_narrative` with presumed risks inserted by code; "PBC GAP" |
| AC-12 | AC2.3 | T19 | Flag conversions are drafts; nothing is sent |
| AC-13 | AC2.4 | T19 | EP-only minutes approval through five layers |
| AC-14 | AC2.5–AC2.6 | T19 | Inquiries are questionnaire drafts; L2 at 4:52 PM |
| AC-15 | AC3.1–AC3.3 | T08, T12 | Engine figures and the preview endpoint; no browser arithmetic |
| AC-16 | AC3.4–AC3.5 | T12, T15 | The card, the decision and v2 in one unit of work; 403 for anyone but the EP |
| AC-17 | AC3.6–AC3.8 | T12 | Reassessment No change and Revise; Granite Peak |
| AC-18 | AC3.9 | T16 | Materiality never on a client surface |
| AC-19 | AC4.1–AC4.3 | T13, T20 | Tally from rows, RMM from policy, the drawer |
| AC-20 | AC4.4–AC4.5 | T18 | One `significant_risk` card; management override never rebuttable |
| AC-21 | AC4.6–AC4.8 | T13, T29 | Linkage, pending suggestions, coverage by code, re-draft consumer |
| AC-22 | AC5.1–AC5.3 | T18, T43 | G4 facts, Northwind timeline, flag off hides G4 |
| AC-23 | AC6.1–AC6.7 | T07, T25, T26, T31 | Pack error text, exceptions, proposals only, routing, narration by code |
| AC-24 | AC7.1–AC7.7 | T31, T35, T37 | 92-day gap, reliance card refusals, request drafts, EP decides reliance |
| AC-25 | AC8.1–AC8.4 | T11, T15 | Drafting gate, number provenance, hostile content, attribution |

## 6. Contract Monday answers (decided; AMENDMENT-solo: decide, record, carry on)
- **OQ-1 (drafter owner):** A-04-T11 owns `workpapers.section_drafter`, its spec, one
  evaluation suite and `SectionDraftWorkflow`; A-05 and A-08 add modes as spec versions; one flag
  `workpapers.drafting`.
- **OQ-3 (G4):** G4 is met iff the current materiality version is decided or reassessed by the EP,
  the latest `significant_risk` card is decided with the register hash unchanged since, and no
  risk has a proposed significance or rebuttal. The card's question includes the audit approach;
  there is no separate L4. Blockers `materiality_pending`, `register_not_approved`,
  `register_changed_after_approval`, `proposal_pending`.
- **OQ-4 (cards):** one `significant_risk` card per approval request with per-subject outcomes;
  `fraud_rebuttal` folds into it.
- **OQ-7 (RMM matrix):** `threshold_policies.kind = rmm_matrix` (expand-only migration M3), BH v1
  loaded through K-02's import endpoint; a platform default only for synthetic test tenants.
- **OQ-13 (Open in Excel):** not an ADR-036 engagement export; an audited single-workpaper
  download with Restricted cells masked and no fresh MFA. The binder export stays the ADR-036 path.
- **OQ-15 (pack error on a pinned engagement):** pack validation resolves a step's template
  references against the pinned version **and** the firm's template library, so adding the
  missing bridge-letter template unblocks Retry; a change to the step itself still needs a new
  methodology version and K-03's update path.

Also recorded: OQ-8 rounding (overall to the policy's `rounding_increment`, default 100, half up;
PM and CT from the rounded overall, whole dollars), OQ-9 (out-of-range rates 422
`rate_outside_policy`), OQ-14 (fresh MFA for `planning_materiality` and `service_org_reliance`,
not `significant_risk`).

## 7. Figures that foot (Brightwater Hale)
Northwind net assets 16,812,400 × 1.5% = 252,186 → 252,200; PM 75% 189,150; CT 5% 12,610; range
1.0%–2.0% → 168,100–336,200; final 16,861,000 → 252,900, difference 700 (0.3%). Granite Peak
3,100,000 × 5% = 155,000 / 116,250 / 7,750. Tally 10 / 2 (+1) / 2 / 3 / 1. SOC gap 92 days.
Exceptions 7 (1 / 3 / 3). Procedures 67, 21 mandatory.

## 8. Open questions
Carried in A-04 §11: OQ-2 (no run until P-10), OQ-5 (no Teams), OQ-6 (questionnaires), OQ-10
(EBP benchmark source), OQ-11 (seed contradictions, resolved in the screen contracts), OQ-12 (pen
test scope).
