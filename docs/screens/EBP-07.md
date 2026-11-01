# EBP-07 · Form 5500 tie-out & supplemental schedules

| Field | Value |
|---|---|
| Route and params | `/audits/$auditId/ebp/form-5500` · `?tab=schedule-h\|part-iv\|schedules` |
| Template and host frame | T3 two-column variant inside the cockpit (rail 330 + tie-out 536 + Form 5500 viewer 490) |
| Surface | firm (never a client surface) |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/EBP-07 Form 5500 tie-out & supplemental schedules/` (README.md, spec.md; no revision file) |
| Epic and tasks | A-05 · SPEC-640 · contract stub A-05-T04 (`docs/contracts/ebp-workpapers.md`) · bundle T05 · migrations T06 and later · seed T07 |
| Manifest status | planned |

## States
| Artboard | Viewer (persona) and clock | Snapshot | Data condition that produces it | Endpoints | Parity tier | Status |
|---|---|---|---|---|---|---|
| a · Consistent | a–e `hannah-leclerc` · Sep 24 10:15 AM | d: no draft; e: draft with 4a "No" | consistent with reconciling items (default) | see API | C | live |
| b · Part IV | a–e `hannah-leclerc` · Sep 24 10:15 AM | d: no draft; e: draft with 4a "No" | Part IV | see API | C | live |
| c · Schedules | a–e `hannah-leclerc` · Sep 24 10:15 AM | d: no draft; e: draft with 4a "No" | Schedules | see API | C | live |
| d · Draft not received | a–e `hannah-leclerc` · Sep 24 10:15 AM | d: no draft; e: draft with 4a "No" | TPA draft not received — empty canvas state: 34px tile FileText, "Draft Form 5500 not received", copy "Summit Plan Administrators uploads it through their request link. The tie-out runs when it arrives.", secondary "Remind Summit" (POR-14) | see API | C | live |
| e · Inconsistent | a–e `hannah-leclerc` · Sep 24 10:15 AM | d: no draft; e: draft with 4a "No" | inconsistent — 4a answered "No" on the draft: row brick Flag "Inconsistent with the late-deposit finding (EBP-04)" + "Raise exception…" | see API | C | live |
| loading, error, not allowed, off | as above | — | the read never answers / 5xx / walled 404 / `ebp.modules` off: C-20 | — | C | live |

## API
| Method and path | Purpose | Action (agent) |
|---|---|---|
| `GET /ebp/form-5500` · `GET /ebp/form-5500/part-iv` · `GET /ebp/form-5500/schedules/{4i\ | 4a}` | Draft status, lines, tallies, Part IV, schedules (`ebp.form5500_tieout`) |
| `POST /ebp/form-5500/lines/{lid}/value` `{value, citation_note}` | Keyed line value when agents are off | `ebp.form5500.key` (deny) |
| `POST /ebp/form-5500/schedules/{kind}/render` | C11 render, byte-stable | `ebp.schedule.render` (deny) |
| `POST /ebp/form-5500/reconciliation-note` | Note 8 to AUD-20 (A-06 receiving endpoint) | `ebp.form5500.send_note` (deny) — manager |
| `POST /ebp/form-5500/remind` | Follow-up draft to Summit; send is P-06's `follow_up.send` | `ebp.form5500.remind` (deny) |

Prefix `/v1/audits/{work_item_id}` unless the path starts with `/v1`. Sign-offs, notes, issues and decision cards are P-04's routes on EBP targets registered with `register_reviewable`.

## Status
Status words come from the generated `status.ts` (C2): the A-05 rows drafted for T05 (`ebp_provision`, `ebp_provider_check`, `ebp_test_result`, `ebp_late_remittance`, `ebp_certification_point`, `ebp_form5500_line`, `estimate`, `related_party`, `party_in_interest`) plus `audit_section`.

## Copy
Verbatim from the handoff (copy keys in `screens/EBP-07/copy.ts` when built). Key strings:
- "Form 5500 Tie-Out"
- "Form 5500 tie-out — Northwind 401(k)"
- "Audits"
- "All Audits"
- "PY2025 Employee Benefit Plan Audit"
- "BH Audit Methodology · EBP v3"
- "Fieldwork"
- "Sort by run"
- "Auto mode"
- "Complete · 9:58 AM"
- "Northwind Robotics 401(k) Plan"
- "PY2025 · Northwind Robotics, Inc."
- "Overview ⌄"
- "Planning ›"
- "5 of 6"
- "SOC 1 waiting on inputs"
- "Fieldwork ⌄"
- "Reviewed · HL"
- "Sep 15, 2026 10:02 AM"
- "Sep 15, 2026 4:40 PM"
- "Prepared · AC"
- "Testing ⌄"
- "In progress · 2 exceptions"
- "In progress"

## Links
| From | To (manifest builder) | Planned or live |
|---|---|---|
| Opens AUD-01 · all audits | AUD-01 `to.AUD01()` | planned until AUD-01 is built |
| Opens AUD-03 · source documents | AUD-03 `to.AUD03()` | planned until AUD-03 is built |
| Opens SHL-09 · where this figure comes from | SHL-09 `to.SHL09()` | planned until SHL-09 is built |
| Opens AUD-20 · FS draft | AUD-20 `to.AUD20()` | planned until AUD-20 is built |
| Opens SHL-15 · then AUD-15 | SHL-15 `to.SHL15()` | planned until SHL-15 is built |
| Opens POR-14 | POR-14 `to.POR14()` | planned until POR-14 is built |
| Opens CLI-02 · client record | CLI-02 `to.CLI02()` | planned until CLI-02 is built |
| Opens EBP-01 · plan profile | EBP-01 `to.EBP01()` | planned until EBP-01 is built |
| Opens KNW-03 · program editor | KNW-03 `to.KNW03()` | planned until KNW-03 is built |
| Opens AUD-29 · activity log | AUD-29 `to.AUD29()` | planned until AUD-29 is built |
| Opens AUD-06 · trial balance | AUD-06 `to.AUD06()` | planned until AUD-06 is built |
| Opens AUD-07 · materiality | AUD-07 `to.AUD07()` | planned until AUD-07 is built |
| Opens AUD-08 · risk assessment | AUD-08 `to.AUD08()` | planned until AUD-08 is built |
| Opens AUD-04 · audit program | AUD-04 `to.AUD04()` | planned until AUD-04 is built |
| Opens AUD-09 · internal control | AUD-09 `to.AUD09()` | planned until AUD-09 is built |
| Opens AUD-10 · service organizations & SOC 1 | AUD-10 `to.AUD10()` | planned until AUD-10 is built |
| Opens EBP-02 · plan provisions review | EBP-02 `to.EBP02()` | planned until EBP-02 is built |
| Opens AUD-11 · sample selection | AUD-11 `to.AUD11()` | planned until AUD-11 is built |
| Opens EBP-06 · investments & certification | EBP-06 `to.EBP06()` | planned until EBP-06 is built |
| Opens EBP-03 · eligibility testing | EBP-03 `to.EBP03()` | planned until EBP-03 is built |
| Opens EBP-04 · contributions & remittance | EBP-04 `to.EBP04()` | planned until EBP-04 is built |
| Opens EBP-05 · distributions & loans | EBP-05 `to.EBP05()` | planned until EBP-05 is built |
| Opens SHL-12 | SHL-12 `to.SHL12()` | planned until SHL-12 is built |
| Inbound | from AUD-11, AUD-12, AUD-19, AUD-21, AUD-27, EBP-02, EBP-03, EBP-04, EBP-05, EBP-06, EBP-08, EBP-09 | planned with each host |

## Acceptance
- EBP-07: every artboard above renders from its fixture scenario at Tier C (A-05 §5.4).
- Notes from the plan: Persona Hannah Leclerc. After AUD-20 (A-06). Viewer shows the TPA's PDF with field regions (P-03 word layer; P-11 OCR when scanned), not a T17 form face (OQ-4). 4i and 4a only (4j answered No). Typed values #6A98E8; no "$" in the statement table

## Deviations
| ID | What differs from the handoff | Why | Decision recorded |
|---|---|---|---|
| DV-EBP-07-1 | Agent-off path: every agent-filled value has a keyed or imported equivalent with a required citation note; the agent states read "not cleared" until A-04's `workpapers.drafting` and the firm's opt-in hold | A-05 F13; ADR-112 | DEC-1857 |

## Parity
| Artboard | Tier | Diff % | Notes |
|---|---|---|---|
| all | C | — | reported once the screen is built |

## Open gaps
None.
