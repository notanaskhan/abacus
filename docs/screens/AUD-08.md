# AUD-08 · Risk assessment register & linkage

| Field | Value |
|---|---|
| Route and params | `/audits/$auditId/risks` · `?tab=register\|linkage&filter=unaddressed` · `?ov=risk:<code>` (O2 drawer 480) · `?ov=decision:<cardId>&subject=<code>` (SHL-11) |
| Template and host frame | T6 WorkbookLayout in the cockpit (control row 42, tally 52, grid) + O2 drawer · `Wave 2 - Audit Planning.dc.html#aud08` |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/AUD-08 Risk assessment register and linkage/` (README.md, spec.md, revision.md R2: Draft with agent, C-31 markers; revision wins) |
| Epic and tasks | A-04 · stubs T01 · register service T13 · approval card and G4 facts T18 · drafter mode `risk` T11 · screen T20 (a, b, b2, d) and T29 (c, e, f, g) · parity T38 · SPEC-620 |
| Manifest status | planned |

## States
| Artboard | Viewer (persona) | Clock | Snapshot | Data condition that produces it | Status |
|---|---|---|---|---|---|
| a | hannah-leclerc | Mon Sep 14, 2026, 2:30 PM | E0 | Ten risks; R3 and R5 routed 12:31 PM; tally RISKS 10 · SIGNIFICANT 2 (+1 proposed) · FRAUD RISKS 2 · HIGH RMM 3 · UNADDRESSED 1 · EP APPROVAL Pending | live |
| b | hannah-leclerc | 2:30 PM | `?ov=risk:R3` | R3 drawer: SAS 145 factors (fraud High; change Moderate; complexity, subjectivity, uncertainty Low), rationale with four citations, versions v1 10:15 AM · v2 12:31 PM; footer "Routed to Margaret Okonkwo · 12:31 PM" + "Remind Margaret…" | live |
| b2 | margaret-okonkwo | 2:30 PM | `?ov=risk:R3` | Partner footer "Approve as significant risk" (opens SHL-11 on the `significant_risk` card with R3 preselected) · "Not significant…" | live |
| c | hannah-leclerc | 2:30 PM | `?tab=linkage` | R1→Journal entries; R2, R3→EBP-04; R4, R5→EBP-06; R6, R7→EBP-05; R9→EBP-09; R10→Parties in interest + EBP-04; R8 has no dot; EBP-03 outlined "Suggested" | live (EBP targets planned until A-05) |
| d | hannah-leclerc | 4:40 PM | E0 | Margaret decided at 4:40 PM: R3 "Approved · MO", R5 "Rebuttal approved · MO", every row "EP approved"; G4 met | live |
| e | hannah-leclerc | 2:30 PM | override | "Revising after Internal Control…": a `risk` run for R3 started by the re-draft consumer, skeleton rows, polling C6 v1 | live; spinner masked until P-09 |
| f | hannah-leclerc | 2:30 PM | `?ov=risk:R8` | R8's rationale, assertions and EBP-03 response arrive as pending suggestions with three citations; "Suggested by Accrued Agent · 3 citations · not yet adopted"; Adopt · Edit · Discard | live with `workpapers.drafting` |
| g | hannah-leclerc | 2:30 PM | interact | "Identify risks with agent": "10 of 10" and "R8" from code facts; nothing added without a person | live; with drafting off the control reads "Check coverage" (code text only) |
| loading, not allowed, off | as AUD-04 | — | — | `assurance.risk_register` off: C-20 state; G4 hidden on ENG-02 | live |

## API
| Read or write | Endpoint | Shape | Matrix action | allowed_actions and read-only reasons per role |
|---|---|---|---|---|
| read | `GET …/risks/register` | `RegisterOut` with `TallyOut` | `risk.read` | the approve controls only for the reserved EP |
| read | `GET …/risks/{rid}` | `RiskDrawerOut` | `risk.read` | — |
| read | `GET …/risks/linkage` | `LinkageOut` | `risk.read` | — |
| write | `PATCH …/risks/{rid}` | `RiskEditIn` (RMM by code; 422 `presumption_not_rebuttable` on R1) | `risk.edit` | EP, manager, senior |
| write | `POST`, `DELETE …/risks/{rid}/responses` | `ResponseIn` | `risk.link` | EP, manager, senior |
| write | `POST …/risks/approval-requests` | `ApprovalRequestOut` (one `significant_risk` card) | `risk.route_for_approval` | manager, senior |
| read | `POST …/risks/coverage` | `CoverageOut` | `risk.read` | — |
| write | `POST …/risks/{rid}/drafts` `{fields}` | 202 `RunStartedOut` | `workpaper.draft` | EP, manager, senior |
| write | `POST /v1/decisions/{id}/decide` (C3) | per-subject outcomes | `decision.decide` | reserved EP only |

## Status
`risk_register_row` (Draft · EP approved · Revised), `risk_significance` (Mandatory · Proposed · Approved · Not significant), `risk_fraud` (Presumed · Rebuttal proposed · Rebuttal approved), `risk_linkage` (Linked · Suggested).

## Copy
Tally labels RISKS · SIGNIFICANT · FRAUD RISKS · HIGH RMM · UNADDRESSED · EP APPROVAL; drawer cards "Inherent risk factors (SAS 145)", "Rationale", "Relevant assertions", "Versions"; "Routed to Margaret Okonkwo · 12:31 PM", "Remind Margaret…", "Approve as significant risk", "Not significant…"; R2: "Draft with agent", "Identify risks with agent", "Suggested by Accrued Agent · n citations · not yet adopted", "Adopt" · "Edit" · "Discard", "Adopted by HL", "Edited by HL · was …".

## Links
| From | To (manifest builder) | Planned or live |
|---|---|---|
| EBP-03…09 columns | EBP screens | planned (A-05); a planned link, never a dead click |
| Approve as significant risk | SHL-11 `?ov=decision:<cardId>&subject=R3` | live (P-04) |
| Open R8 → | `?ov=risk:R8` | live |
| Inbound | AUD-05, AUD-07, AUD-02, HOME-02 | live |

## Acceptance
- AUD-08 acceptance: the tally reconciles to the grid (10; R1 mandatory + R3 proposed = 2 with "1 proposed"; fraud R1, R3; High RMM R1, R3, R8; unaddressed R8).
- AUD-08 acceptance: inherent and control risk are assessed separately, the five SAS 145 factors appear in the drawer and a stand-back line is present.
- AUD-08 acceptance: management override is at the financial-statement level and presumed; the investment-income rebuttal is only proposed.
- AUD-08 acceptance: R3's rationale cites the same $48,600 Dec 26 → Jan 9 deposit as AUD-09 row 2.
- AUD-08 acceptance: only the partner's view shows "Approve as significant risk".
- AUD-08 acceptance (R2): drafted values follow C-31 and change nothing until a person adopts, edits or discards.

## Figures
The tally, RMM (from the firm's `rmm_matrix` policy, BH matrix v1, CR "Max" on every row) and coverage are computed by code; the register hash is stored on approval.

## AVOID
Gradients, emoji, saturated blue, heavy shadows, invented colours, lorem ipsum, zebra rows, heat-map row backgrounds, "$" in the register, the agent approving a significant risk, rebutting the revenue presumption or adopting its own draft; changing R1–R10 ratings in a–e; "task" for a to-do.

## Deviations
| ID | What differs from the handoff | Why | Decision recorded |
|---|---|---|---|
| DV-A8-1 | b2's README viewer is Hannah; the partner footer renders as Margaret | Only the EP sees the approve controls | DEC-1758 |
| DV-A8-2 | R3 reads "9 business days" (the remittance-lag calculator's basis) where the seed says "10 days late" | Different bases; A-05's calculator names its basis | A-04 OQ-11 |
| DV-A8-3 | e's spinner is masked for parity until P-09 | C6 v1 polling, no run store | DEC-1758 |

## Parity
| Artboard | Tier | Diff % | Notes |
|---|---|---|---|
| a–d, f, g | C | — | T38; T6 frame Tier B is F-06's |
| e | C | — | masked spinner; lock moves to P-09's close-out |

## Open gaps
None.
