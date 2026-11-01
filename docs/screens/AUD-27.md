# AUD-27 · Estimates, related parties & parties in interest

| Field | Value |
|---|---|
| Route and params | `/audits/$auditId/estimates` · `?tab=estimates\|related-parties\|parties-in-interest`; `?dock=agent` |
| Template and host frame | T2 record cockpit (rail 330 + canvas 696 + dock 330 Agent) |
| Surface | firm (never a client surface) |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/AUD-27 Estimates, related parties & parties in interest/` (README.md, spec.md; no revision file) |
| Epic and tasks | A-05 · SPEC-640 · contract stub A-05-T04 (`docs/contracts/ebp-workpapers.md`) · bundle T05 · migrations T06 and later · seed T07 |
| Manifest status | planned |

## States
| Artboard | Viewer (persona) and clock | Snapshot | Data condition that produces it | Endpoints | Parity tier | Status |
|---|---|---|---|---|---|---|
| a · Estimates | a, b, d, e `simone-baptiste` · **Tue Oct 6, 2026 11:20 AM**; c `marcus-delaney` · Sep 24 | Granite Peak (a, b, d, e); Northwind (c). `simone-baptiste` must be added to F-04's persona list (R22) | Estimates (default) | see API | C | live |
| b · Related parties | a, b, d, e `simone-baptiste` · **Tue Oct 6, 2026 11:20 AM**; c `marcus-delaney` · Sep 24 | Granite Peak (a, b, d, e); Northwind (c). `simone-baptiste` must be added to F-04's persona list (R22) | Related parties | see API | C | live |
| c · Parties in interest | a, b, d, e `simone-baptiste` · **Tue Oct 6, 2026 11:20 AM**; c `marcus-delaney` · Sep 24 | Granite Peak (a, b, d, e); Northwind (c). `simone-baptiste` must be added to F-04's persona list (R22) | EBP parties-in-interest variant | see API | C | live |
| d · Unevaluated | a, b, d, e `simone-baptiste` · **Tue Oct 6, 2026 11:20 AM**; c `marcus-delaney` · Sep 24 | Granite Peak (a, b, d, e); Northwind (c). `simone-baptiste` must be added to F-04's persona list (R22) | unevaluated — all estimates neutral, dock idle with dark "Run" 32h | see API | C | live |
| e · Exception raised | a, b, d, e `simone-baptiste` · **Tue Oct 6, 2026 11:20 AM**; c `marcus-delaney` · Sep 24 | Granite Peak (a, b, d, e); Northwind (c). `simone-baptiste` must be added to F-04's persona list (R22) | exception raised — Peakline row links "Finding F-3 → AUD-15" | see API | C | live |
| loading, error, not allowed, off | as above | — | the read never answers / 5xx / walled 404 / `ebp.modules` off: C-20 | — | C | live |

## API
| Method and path | Purpose | Action (agent) |
|---|---|---|
| `GET /estimates` · `POST /estimates` · `PUT /estimates/{id}/method` · `POST /estimates/{id}/request-conclusion` | AUD-27 estimates; decision card reserved to the EP (`assurance.estimates_rp`) | `estimate.read` · `estimate.evaluate` (deny) · `estimate.request_conclusion` (deny); deciding is P-04's `decision.decide` with `reserved_role` |
| `GET /related-parties` · `POST /related-parties` · `POST /related-parties/search` · `POST /related-parties/{id}/screen-out` `{reason}` · `POST /related-parties/{id}/ask-management` | AUD-27 related parties | `related_party.read` · `.manage` (deny) · `.search.run` (`agent_run.start`) · `.screen_out` (deny) |
| `GET /parties-in-interest` · `POST /parties-in-interest` · `GET /prohibited-transactions` | AUD-27c; PT reads the late remittance | `ebp.read` · `party_in_interest.manage` (deny) |

Prefix `/v1/audits/{work_item_id}` unless the path starts with `/v1`. Sign-offs, notes, issues and decision cards are P-04's routes on EBP targets registered with `register_reviewable`.

## Status
Status words come from the generated `status.ts` (C2): the A-05 rows drafted for T05 (`ebp_provision`, `ebp_provider_check`, `ebp_test_result`, `ebp_late_remittance`, `ebp_certification_point`, `ebp_form5500_line`, `estimate`, `related_party`, `party_in_interest`) plus `audit_section`.

## Copy
Verbatim from the handoff (copy keys in `screens/AUD-27/copy.ts` when built). Key strings:
- "Estimates & related parties — Granite Peak"
- "Audits"
- "All Audits"
- "FY2026 Financial Statement Audit"
- "BH Audit Methodology · FS v5"
- "Fieldwork"
- "Sort by run"
- "Auto mode"
- "Granite Peak Outdoor Supply, Inc."
- "FYE 6/30/2026 · FS audit"
- "Planning ›"
- "8 of 8 ✓"
- "Reviewed · HL"
- "In progress · 1 exception"
- "In progress · 40 selected"
- "In progress"
- "In progress · 1 candidate"
- "Estimates & Related Parties"
- "Edit"
- "Sign off…"
- "Source Docs"
- "Estimates (on) · Related parties 1"
- "Open in Excel"
- "Estimates"

## Links
| From | To (manifest builder) | Planned or live |
|---|---|---|
| Opens CLI-02 · client record | CLI-02 `to.CLI02()` | planned until CLI-02 is built |
| Opens KNW-03 · program editor | KNW-03 `to.KNW03()` | planned until KNW-03 is built |
| Opens AUD-03 · source documents | AUD-03 `to.AUD03()` | planned until AUD-03 is built |
| Opens AUD-29 · activity log | AUD-29 `to.AUD29()` | planned until AUD-29 is built |
| Opens AUD-11 · sampling | AUD-11 `to.AUD11()` | planned until AUD-11 is built |
| Opens AUD-12 · Controls Testing — Revenue Cycle | AUD-12 `to.AUD12()` | planned until AUD-12 is built |
| Opens AUD-20 | AUD-20 `to.AUD20()` | planned until AUD-20 is built |
| Opens SHL-11 · the conclusion is reserved to Margaret Okonkwo | SHL-11 `to.SHL11()` | planned until SHL-11 is built |
| Opens EBP-01 · plan profile | EBP-01 `to.EBP01()` | planned until EBP-01 is built |
| Opens AUD-06 · trial balance | AUD-06 `to.AUD06()` | planned until AUD-06 is built |
| Opens AUD-07 · materiality | AUD-07 `to.AUD07()` | planned until AUD-07 is built |
| Opens AUD-08 · risk assessment | AUD-08 `to.AUD08()` | planned until AUD-08 is built |
| Opens AUD-04 · audit program | AUD-04 `to.AUD04()` | planned until AUD-04 is built |
| Opens AUD-09 · internal control | AUD-09 `to.AUD09()` | planned until AUD-09 is built |
| Opens AUD-10 · service organizations & SOC 1 | AUD-10 `to.AUD10()` | planned until AUD-10 is built |
| Opens EBP-02 · plan provisions review | EBP-02 `to.EBP02()` | planned until EBP-02 is built |
| Opens EBP-06 · investments & certification | EBP-06 `to.EBP06()` | planned until EBP-06 is built |
| Opens EBP-03 · eligibility testing | EBP-03 `to.EBP03()` | planned until EBP-03 is built |
| Opens EBP-04 · contributions & remittance | EBP-04 `to.EBP04()` | planned until EBP-04 is built |
| Opens EBP-05 · distributions & loans | EBP-05 `to.EBP05()` | planned until EBP-05 is built |
| Opens EBP-08 · participant accounts | EBP-08 `to.EBP08()` | planned until EBP-08 is built |
| Opens EBP-07 · Form 5500 tie-out | EBP-07 `to.EBP07()` | planned until EBP-07 is built |
| Simone raised Finding F-3 on Peakline Freight LLC; it stays open in AUD-15 until management answers | AUD-15 `to.AUD15()` | planned until AUD-15 is built |
| Inbound | from AUD-08 | planned with each host |

## Acceptance
- AUD-27: every artboard above renders from its fixture scenario at Tier C (A-05 §5.4).
- Notes from the plan: Personas Simone Baptiste (a, b, d, e; Granite Peak, Tue Oct 6, 11:20 AM) and Marcus Delaney (c). Two tabs per engagement type. Status words only Unevaluated · Evaluated · Exception (+ muted Screened out); "Evaluated · pending EP" is a pill display variant. PT reads the EBP-04 `late_remittance`; the agent never concludes

## Deviations
| ID | What differs from the handoff | Why | Decision recorded |
|---|---|---|---|
| DV-AUD-27-1 | Agent-off path: every agent-filled value has a keyed or imported equivalent with a required citation note; the agent states read "not cleared" until A-04's `workpapers.drafting` and the firm's opt-in hold | A-05 F13; ADR-112 | DEC-1857 |

## Parity
| Artboard | Tier | Diff % | Notes |
|---|---|---|---|
| all | C | — | reported once the screen is built |

## Open gaps
None.
