# AUD-09 · Internal control & exceptions

| Field | Value |
|---|---|
| Route and params | `/audits/$auditId/controls` · `?sheet=exceptions\|internal-control&cell=D2` · O1 severity picker in local state |
| Template and host frame | T2 RecordCockpit with dock (rail 330 · canvas 696 spreadsheet grid · dock 330); AuditBar run variant (DF-39) · `Wave 2 - Audit Planning.dc.html#aud09` |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/AUD-09 Internal control and exceptions/` (README.md, spec.md; no revision) |
| Epic and tasks | A-04 · stubs T01 · tables T25 · services T25/T31 · pack validation T07 · drafter mode `ic` T11 · screen T26 · parity T38 · SPEC-620 |
| Manifest status | planned |

## States
| Artboard | Viewer (persona) | Clock | Snapshot | Data condition that produces it | Status |
|---|---|---|---|---|---|
| a | hannah-leclerc | Mon Sep 14, 2026, 12:24 PM | E0 | Exceptions rows 2–8 hold 7 exceptions (1 Significant deficiency, 3 Deficiency, 3 Exception for resolution) with COSO components; the risk re-draft started 12:20 is running | live; dock run card on C6 v1 (P-09's ToolCard planned) |
| b | hannah-leclerc | 12:24 PM | `?cell=D2` | Footer "Exceptions!D2 · 2 citations — PayGrid Contribution Detail 2025.xlsx (pay date 12/26/2025) · Keystone Account Balances PY2025.xlsx (deposit 1/9/2026)" | live |
| c | hannah-leclerc | 12:24 PM | interact | Severity picker on D2: Deficiency · Significant deficiency · Material weakness as a proposal; "Concluding severity is reserved to the engagement partner (Findings)." | live |
| d | hannah-leclerc | 9:58 AM | E0 | The seeded failure: "Pack configuration error: BH-EBP-140 step 8 points to a SOC 1 bridge-letter template that EBP v3 does not include. No evidence written."; Retry; "Fix in Knowledge →" opens KNW-03 f at step 8; rail Internal Control "Failed — see run"; grid header only and "No evidence written." | live |
| e | hannah-leclerc | 12:24 PM | `?sheet=internal-control` | Processes × Walkthrough · Design · Implementation · Reliance; row 4 links to AUD-10 | live |
| f | margaret-okonkwo | Thu Sep 24, 2026 | fixture read-through | D2 "Significant deficiency · Concluded MO" and "Communicated" from A-06 and A-07 records | live once A-06 and A-07 register; fixture before |
| loading, not allowed, off | as AUD-04 | — | — | `assurance.internal_control` off: C-20 state | live |

## API
| Read or write | Endpoint | Shape | Matrix action | allowed_actions and read-only reasons per role |
|---|---|---|---|---|
| read | `GET …/internal-control/exceptions` | `ControlExceptionOut[]` with `address` | `control.read` | — |
| read · write | `GET`, `PUT …/internal-control/processes[/{id}]` | `ProcessOut`, `ProcessIn` | `control.read` · `control.edit` | team edits |
| write | `PATCH …/exceptions/{row}/proposed-severity` | `ProposedSeverityIn` | `deficiency.propose_severity` | EP, manager, senior; never a conclusion |
| write | `POST …/exceptions/{row}/send-to-findings` · `/convert-to-misstatement` | `RoutedOut` (503 `route_not_available` until A-06 registers; the menu item hides) | `exception.route` | EP, manager, senior |
| write | `POST …/exceptions/{row}/request-evidence` | `RequestDraftOut` (SHL-14 prefill) | `request_item.create` | as that action |
| write | `POST …/workpapers/{id}/drafts` `{mode: ic}` | 202 | `workpaper.draft` | Retry starts a new run |

## Status
`deficiency_severity` (proposal words), `control_exception_disposition`, `control_design`, `audit_section` ("Failed — see run").

## Copy
"Internal Control · Exceptions", "Open in Excel", the failed-step text above (identical to AUD-02 e), "Retry", "Fix in Knowledge →", "Proposed by Accrued Agent. Concluding severity is reserved to the engagement partner (Findings).", "Open in Findings", "No evidence written."

## Links
| From | To (manifest builder) | Planned or live |
|---|---|---|
| Send to Findings, Open in Findings | AUD-15 | planned (A-06) |
| Convert to misstatement | AUD-16 | planned (A-06) |
| Fix in Knowledge → | KNW-03 f at BH-EBP-140 step 8 | live (K-01) |
| Row 4 | AUD-10 | live once T37 lands |
| Request evidence… | SHL-14 | live (P-04) |
| Opens AUD-01 · all audits | AUD-01 | handoff link (status in the manifest) |
| Opens CLI-02 | CLI-02 | handoff link (status in the manifest) |
| Opens AUD-03 | AUD-03 | handoff link (status in the manifest) |
| Opens SHL-12 for the whole run | SHL-12 | handoff link (status in the manifest) |
| Opens WB-09 · run trace | WB-09 | handoff link (status in the manifest) |
| Opens AUD-06 | AUD-06 | handoff link (status in the manifest) |
| Opens AUD-07 | AUD-07 | handoff link (status in the manifest) |
| Opens AUD-08 | AUD-08 | handoff link (status in the manifest) |
| Opens AUD-04 | AUD-04 | handoff link (status in the manifest) |
| Opens AUD-11 | AUD-11 | fixture build (handoff link) |
| Opens AUD-12 | AUD-12 | handoff link (status in the manifest) |

## Acceptance
- AUD-09 acceptance: the severity column holds only AU-C 265 words or "Exception for resolution"; COSO components sit in their own column.
- AUD-09 acceptance: counts 1 Significant deficiency, 3 Deficiency, 3 Exception for resolution = 7.
- AUD-09 acceptance: the $48,600 Dec 26 → Jan 9 facts agree with AUD-08 R3; the loan offsets (3, $14,850) and missed deferrals (4) agree with the seed.
- AUD-09 acceptance: true sheet addresses, header row 1, data rows 2–8.
- AUD-09 acceptance: the failed-step state is the one seeded failure with the canonical BH-EBP-140 step 8 text; Trial Balance is not the failing step.

## Figures
Row 3's narration states the comparison by code: 48,600 below PM 189,150 and above CT 12,610 (never "PM $252,200").

## AVOID
Gradients, emoji, saturated blue, heavy shadows, invented colours, lorem ipsum; COSO words in the severity column; the agent concluding a severity; off-by-one sheet addresses; the words Accrual, Arc, ACME, LSA.

## Deviations
| ID | What differs from the handoff | Why | Decision recorded |
|---|---|---|---|
| DV-A9-1 | The narration's "below PM $252,200" is rendered as the code's labelled comparison (PM 189,150; CT 12,610) | The handoff mislabels overall materiality as PM | A-04 OQ-11 |
| DV-A9-2 | "Sort by run" and "Sign off run" are planned (P-10); one AuditBar with a run variant | DF-39 | DEC-1758 |
| DV-A9-3 | Retry passes once the bridge-letter template exists in the firm's template library, without a new methodology version | OQ-15 | DEC-1758 |
| DV-A9-4 | a and d's dock regions are masked for parity | No engagement run until P-10 (OQ-2) | DEC-1758 |

## Parity
| Artboard | Tier | Diff % | Notes |
|---|---|---|---|
| b, c, e | C | — | T38 |
| a, d | C | — | dock masked; locks move to P-09 |
| f | C | — | locks when A-06 registers |

## Open gaps
None.
