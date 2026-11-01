# EBP-09 · Administrative expenses & operational compliance

| Field | Value |
|---|---|
| Route and params | `/audits/$auditId/ebp/admin-expenses` · `?tab=expenses\|compliance\|qualification`; `?cell=G4` |
| Template and host frame | T6 grammar inside the T2 cockpit, spreadsheet grid |
| Surface | firm (never a client surface) |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/EBP-09 Administrative expenses & operational compliance/` (README.md, spec.md; no revision file) |
| Epic and tasks | A-05 · SPEC-640 · contract stub A-05-T04 (`docs/contracts/ebp-workpapers.md`) · bundle T05 · migrations T06 and later · seed T07 |
| Manifest status | planned |

## States
| Artboard | Viewer (persona) and clock | Snapshot | Data condition that produces it | Endpoints | Parity tier | Status |
|---|---|---|---|---|---|---|
| a · Administrative expenses | a–e `marcus-delaney` · Sep 24 10:15 AM | d: fixture-only $1,200 undisclosed charge | Administrative expenses, agent draft (default) | see API | C | live |
| b · Operational compliance | a–e `marcus-delaney` · Sep 24 10:15 AM | d: fixture-only $1,200 undisclosed charge | Operational compliance | see API | C | live |
| c · Plan qualification | a–e `marcus-delaney` · Sep 24 10:15 AM | d: fixture-only $1,200 undisclosed charge | Plan qualification | see API | C | live |
| d · Exception variant | a–e `marcus-delaney` · Sep 24 10:15 AM | d: fixture-only $1,200 undisclosed charge | exception — an expense not in the 408(b)(2) disclosure: row amber cell + TriangleAlert "No disclosure on file for $1,200.00 'participant notice mailing'" + "Raise exception…" (illustrative) | see API | C | fixture-only (illustrative) |
| e · Reviewed | a–e `marcus-delaney` · Sep 24 10:15 AM | d: fixture-only $1,200 undisclosed charge | consistent / signed — "✓ HL", rail "Reviewed · HL" | see API | C | live |
| loading, error, not allowed, off | as above | — | the read never answers / 5xx / walled 404 / `ebp.modules` off: C-20 | — | C | live |

## API
| Method and path | Purpose | Action (agent) |
|---|---|---|
| `GET /ebp/plan-expenses` · `GET /ebp/erisa-budget-account` · `GET /ebp/compliance-tests` · `GET /ebp/plan-qualification` · `POST /ebp/plan-expenses/{id}/request-support` | EBP-09; support → SHL-14 prefill | `ebp.read` · `ebp.provider.request` (deny) |
| `GET /v1/workpapers/{wp}/cells/{addr}/citations` | Sheet!Cell footer (A-04 route; EBP maps registered by T09) | `workpaper.read` |

Prefix `/v1/audits/{work_item_id}` unless the path starts with `/v1`. Sign-offs, notes, issues and decision cards are P-04's routes on EBP targets registered with `register_reviewable`.

## Status
Status words come from the generated `status.ts` (C2): the A-05 rows drafted for T05 (`ebp_provision`, `ebp_provider_check`, `ebp_test_result`, `ebp_late_remittance`, `ebp_certification_point`, `ebp_form5500_line`, `estimate`, `related_party`, `party_in_interest`) plus `audit_section`.

## Copy
Verbatim from the handoff (copy keys in `screens/EBP-09/copy.ts` when built). Key strings:
- "ERISA 408(b)(2) service-provider fee disclosure"
- "Admin expenses & compliance — Northwind 401(k)"
- "Audits"
- "All Audits"
- "PY2025 Employee Benefit Plan Audit"
- "BH Audit Methodology · EBP v3"
- "Fieldwork"
- "Sort by run"
- "Auto mode"
- "Admin Expenses & Compliance"
- "Complete · 10:08 AM"
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

## Links
| From | To (manifest builder) | Planned or live |
|---|---|---|
| Opens AUD-15 · Findings | AUD-15 `to.AUD15()` | planned until AUD-15 is built |
| Opens the source with this line lit (SHL-08) | SHL-08 `to.SHL08()` | planned until SHL-08 is built |
| Opens CLI-02 · client record | CLI-02 `to.CLI02()` | planned until CLI-02 is built |
| Opens EBP-01 · plan profile | EBP-01 `to.EBP01()` | planned until EBP-01 is built |
| Opens KNW-03 · program editor | KNW-03 `to.KNW03()` | planned until KNW-03 is built |
| Opens AUD-03 · source documents | AUD-03 `to.AUD03()` | planned until AUD-03 is built |
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
| Opens EBP-08 · participant accounts | EBP-08 `to.EBP08()` | planned until EBP-08 is built |
| Opens EBP-07 · Form 5500 tie-out | EBP-07 `to.EBP07()` | planned until EBP-07 is built |
| Opens SHL-12 · sign off as preparer (L1) | SHL-12 `to.SHL12()` | planned until SHL-12 is built |
| Opens AUD-12 · contribution test | AUD-12 `to.AUD12()` | planned until AUD-12 is built |
| Inbound | from AUD-08, AUD-12, EBP-08 | planned with each host |

## Acceptance
- EBP-09: every artboard above renders from its fixture scenario at Tier C (A-05 §5.4).
- Notes from the plan: Persona Marcus Delaney. Limits per plan year (2025: 23,500 · 7,500 · 11,250 · 70,000 · 350,000); prior-year limits are an AVOID. Tally scope labelled per tab

## Deviations
| ID | What differs from the handoff | Why | Decision recorded |
|---|---|---|---|
| DV-EBP-09-1 | Agent-off path: every agent-filled value has a keyed or imported equivalent with a required citation note; the agent states read "not cleared" until A-04's `workpapers.drafting` and the firm's opt-in hold | A-05 F13; ADR-112 | DEC-1857 |
| DV-EBP-09-2 | State d is illustrative: fixture-only; real data reaches it, the seed default does not | The README marks it illustrative | DEC-1857 |

## Parity
| Artboard | Tier | Diff % | Notes |
|---|---|---|---|
| all | C | — | reported once the screen is built |

## Open gaps
None.
