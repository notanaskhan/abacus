# AUD-07 · Materiality & partner decision

| Field | Value |
|---|---|
| Route and params | `/audits/$auditId/materiality` · `?version=` · `?ov=decision:<cardId>` (SHL-11) · `?dock=agent` |
| Template and host frame | T2 RecordCockpit with dock (rail 330 · canvas 696 · dock 330) + SHL-11 inline · `Wave 2 - Audit Planning.dc.html#aud07` |
| Surface | firm (never a client surface, AC3.9) |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/AUD-07 Materiality - partner decision/` (README.md, spec.md, revision.md R2: prior-year columns; revision wins) |
| Epic and tasks | A-04 · stubs T01 (`docs/contracts/audit-planning.md`) · engine T08 · service and card T12 · recommender T15 · screen T10 · goldens T17 · parity T40 (before the Oct 26 flip) · SPEC-620 |
| Manifest status | planned |

## States
| Artboard | Viewer (persona) | Clock | Snapshot | Data condition that produces it | Status |
|---|---|---|---|---|---|
| a | margaret-okonkwo | Mon Sep 14, 2026, 11:08 AM | E0 | v1 Proposed by Marcus Delaney via Agent at 9:27 AM; `planning_materiality` card awaiting the EP; 1.5% preselected with "Recommended by Accrued Agent"; Decide disabled until a rationale exists | live |
| b | hannah-leclerc | 11:08 AM | E0 | Radios disabled; banner "Only the engagement partner can decide materiality."; footer "Remind Margaret" only | live |
| c | margaret-okonkwo | 11:12 AM | E0 | Decided: card collapses to "✓ Decided by Margaret Okonkwo · Sep 14 11:12 AM · 1.5% of net assets = $252,200"; pill "Version 2 · Decided"; v1 Superseded; rail "Complete · 11:12 AM" | live; the dock line "Resuming the run." is masked until P-10 |
| d | margaret-okonkwo | Tue Oct 6, 2026, 11:20 AM | Oct 6 snapshot | Reassessment at final: 16,861,000 × 1.5% = $252,900; difference $700 (0.3%); "No change"; v3 "Reassessed at final · Margaret Okonkwo · Oct 6 · no change" | live |
| e | margaret-okonkwo | 11:08 AM | override | Revised (layout only): amber "Revised" pill and the impact list of workpapers to re-run | fixture; the live path renders when a Revise is recorded |
| loading, not allowed, off | as AUD-04 | — | — | `assurance.materiality` off: the C-20 state | live |

R2 in every state: PY2024 and PY2023 columns, 48×16 sparklines (`--d1`), the "Overall materiality used" row and the two-sentence caption.

## API
| Read or write | Endpoint | Shape | Matrix action | allowed_actions and read-only reasons per role |
|---|---|---|---|---|
| read | `GET …/materiality/current` | `MaterialityRecordOut` | `materiality.read` | `decision.decide` only for the reserved EP; Hannah gets `decision.notify` |
| read | `POST …/materiality/preview` | `ThresholdsOut` (the browser does no arithmetic) | `materiality.read` | — |
| write | `POST …/materiality/proposals` | `MaterialityProposalOut` | `materiality.propose` | manager, senior |
| write | `POST …/materiality/reassessments` | `ReassessmentRaisedOut` | `materiality.reassess` | manager, senior |
| write | `POST /v1/decision-cards/{card_id}/decide` (C3; fresh MFA; rationale) | decision | `decision.decide` | reserved EP only; 403 for anyone else and for the agent; 422 `rationale_required` |
| write | `POST /v1/decision-cards/{card_id}/notify` | — | `decision.notify` | manager, senior |

## Status
`materiality_version` (Proposed, Decided, Reassessed at final, Revised; Superseded derived), `audit_section` ("Blocked on a partner decision", "Complete · {time}").

## Copy
Verbatim from spec.md and revision.md: "Which planning materiality should this audit use?", "Reserved to Engagement Partner", the three option lines and their PM/CT sub-lines, "Rationale (required for the file)", "Request more analysis…", "Decide", "Benchmarks — unadjusted at 12/31/2025", the R2 caption sentences, "Only the engagement partner can decide materiality.", "Remind Margaret", "Reassessment at final".

## Links
| From | To (manifest builder) | Planned or live |
|---|---|---|
| Benchmark amount | AUD-06 with the source line lit | live (A-02) |
| Citation chips | SHL-07 → KNW-03 | live |
| Request more analysis… | dock composer | planned (P-09); records an analysis request through C3 today |
| Inbound | HOME-02, SHL-04, AUD-02 rail | live |

## Acceptance
- AUD-07 acceptance: 1.5% × 16,812,400 = 252,186 → $252,200; PM 75% = $189,150; CT 5% = $12,610; 1.0% = $168,100 (PM $126,075, CT $8,405); 2.0% bound $336,200.
- AUD-07 acceptance: materiality is computed on unadjusted net assets; v3 at final recomputes on 16,861,000 → $252,900 with no change.
- AUD-07 acceptance: specific benchmarks: contributions 1,318,300 → 39,500–65,900; benefit payments 812,650 → 24,400–40,600.
- AUD-07 acceptance (R2): PY2025 values unchanged; PY2024 14,228,500; 213,400 and 178,500 are 1.5% rounded to 100; growth 18.2%.
- AUD-07 acceptance: the decision card uses SHL-11's grammar and says "Reserved to Engagement Partner".
- AUD-07 acceptance: no "$" in the benchmark table; ranges written "1.0%–2.0%".

## Figures
Every figure above, from the materiality engine (T08) with `engine_version` and `inputs_hash`; goldens in `backend/tests/golden/materiality/` (T17). Granite Peak (FS policy 3%–7% of pre-tax income): 5% = 155,000 / 116,250 / 7,750.

## AVOID
Gradients, emoji, saturated blue, heavy shadows, invented colours, lorem ipsum; the agent deciding (its recommendation is a tag; Decide stays a human click with a written rationale); materiality on any client surface; "$" in the benchmark table; prior-year figures changing today's thresholds.

## Deviations
| ID | What differs from the handoff | Why | Decision recorded |
|---|---|---|---|
| DV-A7-1 | The decision is 11:12 AM; P-04's SHL-11 c artboard keeps 10:02 | DF-34; P-04 Q9 | A-04 OQ-11 |
| DV-A7-2 | c's dock line "Resuming the run." and a's run narration are masked for parity | No engagement run until P-10 (OQ-2) | DEC-1758 |
| DV-A7-3 | Only in-range options are offered; out of range is 422 `rate_outside_policy` | OQ-9 | A-04 OQ-9 |

## Parity
| Artboard | Tier | Diff % | Notes |
|---|---|---|---|
| a–e | C | — | lock before the Oct 26 flip (T40); dock regions masked in c |

## Open gaps
None.
