# AUD-05 · Narrative workpaper (Risk Assessment: Understanding · Risk · Fraud)

| Field | Value |
|---|---|
| Route and params | `/audits/$auditId/narrative/$wpRef` · `?tab=risk\|fraud\|summary\|approach\|linkage` (summary and linkage route to AUD-08) · `?ov=request:new&prefill=<flagId>` (SHL-14) |
| Template and host frame | T2 RecordCockpit without dock (rail 330 · canvas 1036) + SHL-07 guidance variant · `Wave 2 - Audit Planning.dc.html#aud05` |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/AUD-05 Narrative workpaper - Risk Assessment -understanding- risk- frau/` (README.md, spec.md; no revision) |
| Epic and tasks | A-04 · stubs T01 · cell store T04 · fraud brainstorm and flags T19 · drafter mode `risk_narrative` T11 · screen T27 · parity T38 · SPEC-620 |
| Manifest status | planned |

## States
| Artboard | Viewer (persona) | Clock | Snapshot | Data condition that produces it | Status |
|---|---|---|---|---|---|
| a | marcus-delaney | Mon Sep 14, 2026, 2:30 PM | E0 | Menu 1 (understanding the plan) and Menu 2 (overall risks and fraud) with 9 verified citations; presumed fraud risks inserted by code from BH-EBP-110 step 9's `prepopulates`; amber PBC GAP rows; guidance popover "BH Audit Methodology · EBP v3 · mandatory" | live |
| b | marcus-delaney | 2:30 PM | `?tab=fraud` | Session Thu Sep 10, 10:00–10:45 AM CT, led by Margaret Okonkwo; attendees MO, HL, MD, Ana Cruz; "Thomas Whitcombe (EQR) is not invited, to keep his review objective."; discussion rows from step 9; presumed-risk conclusions; inquiries (Dana Kowalski and the payroll administrator Answered Sep 11; the benefits committee chair Requested); minutes "Awaiting EP approval" | live (minutes by a person); the "Drafted by Accrued Agent from the Teams transcript" line is fixture |
| c | marcus-delaney | 2:30 PM | interact | Escalate… on the PBC GAP row opens SHL-14 prefilled as a draft linked to the row; nothing is sent; review note and Remind… are the other conversions | live |
| d | marcus-delaney | 4:52 PM | E0 | Hannah's L2: pill "Reviewed · HL"; the amber notes keep their history | live |
| e | marcus-delaney | 2:30 PM | override | Version 2 drafted by the agent before adoption (outlined ticks) | live with `workpapers.drafting`; fixture until mode `risk_narrative` is cleared |
| loading, not allowed, off | as AUD-04 | — | — | as AUD-04 | live |

## API
| Read or write | Endpoint | Shape | Matrix action | allowed_actions and read-only reasons per role |
|---|---|---|---|---|
| read | `GET …/workpapers/{id}/record?tab=risk` | `WorkpaperRecordOut` with `flags` | `workpaper.read` | — |
| write | `POST …/workpapers/{id}/flags/{flag}/convert` `{to}` | `FlagConvertedOut` | `attention_flag.convert` | EP, manager, senior, staff |
| write | `POST …/workpapers/{id}/flags/{flag}/remind` | follow-up draft | `follow_up.draft` | as that action |
| read | `GET …/fraud-brainstorm` | `FraudSessionOut` | `fraud_session.read` | — |
| write | `PUT …/fraud-brainstorm`, `PUT …/fraud-brainstorm/minutes` | `FraudSessionIn`, `MinutesIn` | `fraud_session.edit` | EP, manager, senior |
| write | `POST …/fraud-brainstorm/minutes/approve` `{minutes_hash}` | `FraudSessionOut` | `fraud_minutes.approve` | engagement partner only; Marcus, Hannah, the agent and a support session are refused (AC2.4) |
| read · write | `GET`, `POST …/fraud-inquiries` | `FraudInquiryOut` (a POR-05 questionnaire draft through C5) | `fraud_session.read` · `fraud_inquiry.request` | manager, senior create; a person sends |

## Status
`attention_flag` ("PBC GAP"), `fraud_minutes`, `fraud_inquiry`, `risk_fraud` (Presumed · Rebuttal proposed), `audit_section`, `workpaper_value_state`.

## Copy
"MENU 1 —", "MENU 2 —"; "PBC GAP" (never "scope limitation"); presumed-risk pills "Significant · cannot be rebutted", "Retained", "Rebuttal proposed"; "Awaiting EP approval"; "Approve minutes"; "Remind…", "Escalate…"; "Citations (9) · Procedures (1)".

## Links
| From | To (manifest builder) | Planned or live |
|---|---|---|
| "?" guidance ↗ | KNW-03 at BH-EBP-110 step 9 | live (K-01) |
| Open register, Summary, Linkage | AUD-08 | live with T20 |
| Escalate… | SHL-14 prefill | live (P-04) |
| Inquiry rows | POR-05 firm preview | live once T-02's questionnaires land (OQ-6) |
| Committee chair | POR-15 | planned (R-02) |
| Planning letter | AUD-22 | planned (A-07) |
| Opens AUD-01 · all audits | AUD-01 | handoff link (status in the manifest) |

## Acceptance
- AUD-05 acceptance: management override is mandatory and cannot be rebutted; the contributions presumption is retained and the investment-income rebuttal is only proposed.
- AUD-05 acceptance: plan facts agree with the seed (PN 001, Keystone ID 58217, QACA 6% default +1% to 15%, 286 participants at BOY, §103(a)(3)(C), Harborline certifies).
- AUD-05 acceptance: the brainstorm is led by the EP, does not invite the EQR, lists individual inquiry responses and has minutes awaiting EP approval.
- AUD-05 acceptance: the amber flag says "PBC GAP", not "scope limitation".

## Figures
9 citations on a; 3 inquiries (2 Answered Sep 11, 1 Requested).

## AVOID
Gradients, emoji, saturated blue, heavy shadows, invented colours, lorem ipsum; "scope limitation"; the agent rebutting a presumption on its own; AU-C paragraph numbers in chrome; the words Accrual, Arc, ACME, LSA, Living Robotics.

## Deviations
| ID | What differs from the handoff | Why | Decision recorded |
|---|---|---|---|
| DV-A5-1 | b's minutes card reads "Written by <person>" on the live path; "Minutes drafted by Accrued Agent from the Teams transcript" stays fixture-only | No transcript connector (OQ-5); connectors only read | DEC-1758 |
| DV-A5-2 | The medium "Microsoft Teams" is stored as the meeting medium only; no Teams integration | OQ-5 | DEC-1758 |
| DV-A5-3 | If T-02's questionnaires are not live by S25, inquiries render as request items with a text answer | OQ-6 | A-04 OQ-6 |

## Parity
| Artboard | Tier | Diff % | Notes |
|---|---|---|---|
| a–e | C | — | locks with T38 |

## Open gaps
None.
