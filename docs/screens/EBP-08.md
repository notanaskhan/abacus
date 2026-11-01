# EBP-08 · Participant accounts summary

| Field | Value |
|---|---|
| Route and params | `/audits/$auditId/ebp/participants` · `?tab=rollforward\|brokerwindow\|vesting`; `?ov=group:<key>` |
| Template and host frame | T6 grammar inside the T2 cockpit |
| Surface | firm (never a client surface) |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/EBP-08 Participant accounts summary/` (README.md, spec.md; no revision file) |
| Epic and tasks | A-05 · SPEC-640 · contract stub A-05-T04 (`docs/contracts/ebp-workpapers.md`) · bundle T05 · migrations T06 and later · seed T07 |
| Manifest status | planned |

## States
| Artboard | Viewer (persona) and clock | Snapshot | Data condition that produces it | Endpoints | Parity tier | Status |
|---|---|---|---|---|---|---|
| a · Agent running | a–c `marcus-delaney` · Sep 24 10:15 AM; d 10:21 AM; e **Fri Sep 25** | a: running; e: L3 HL + L4 MO | agent running (default for this frame) — the table renders with real header and skeleton body rows (9px bars, pulse), tally cards "Pending", a 43h running pill bottom-center "Running participant accounts agent" with spinner | see API | C | live |
| b · BrokerWindow | a–c `marcus-delaney` · Sep 24 10:15 AM; d 10:21 AM; e **Fri Sep 25** | a: running; e: L3 HL + L4 MO | BrokerWindow | see API | C | live |
| c · Vesting | a–c `marcus-delaney` · Sep 24 10:15 AM; d 10:21 AM; e **Fri Sep 25** | a: running; e: L3 HL + L4 MO | Vesting | see API | C | live |
| d · Complete | a–c `marcus-delaney` · Sep 24 10:15 AM; d 10:21 AM; e **Fri Sep 25** | a: running; e: L3 HL + L4 MO | complete — the table above, tally all [tie], rail olive ✓ "Complete · 10:21 AM" | see API | C | live |
| e · Signed off | a–c `marcus-delaney` · Sep 24 10:15 AM; d 10:21 AM; e **Fri Sep 25** | a: running; e: L3 HL + L4 MO | signed off — header chips "✓ HL" (L3 review) and "✓ MO" (L4 partner approval), rail olive ✓ "Signed off" (§3.3.1 reserves "Signed off" for L4; mirrors the reference's "Participant Accounts Summary · Signed off"); before MO signs, the rail reads "Reviewed · HL" | see API | C | live |
| loading, error, not allowed, off | as above | — | the read never answers / 5xx / walled 404 / `ebp.modules` off: C-20 | — | C | live |

## API
| Method and path | Purpose | Action (agent) |
|---|---|---|
| `POST /ebp/participant-accounts/run` · `GET /ebp/participant-accounts/rollforward` · `GET …/groups/{g}/accounts` · `GET …/sdba` · `GET …/vesting` | EBP-08 | `agent_run.start` · `ebp.read` |

Prefix `/v1/audits/{work_item_id}` unless the path starts with `/v1`. Sign-offs, notes, issues and decision cards are P-04's routes on EBP targets registered with `register_reviewable`.

## Status
Status words come from the generated `status.ts` (C2): the A-05 rows drafted for T05 (`ebp_provision`, `ebp_provider_check`, `ebp_test_result`, `ebp_late_remittance`, `ebp_certification_point`, `ebp_form5500_line`, `estimate`, `related_party`, `party_in_interest`) plus `audit_section`.

## Copy
Verbatim from the handoff (copy keys in `screens/EBP-08/copy.ts` when built). Key strings:
- "Participant Accounts Summary · Signed off"
- "Participant accounts — Northwind 401(k)"
- "Audits"
- "All Audits"
- "PY2025 Employee Benefit Plan Audit"
- "BH Audit Methodology · EBP v3"
- "Fieldwork"
- "Sort by run"
- "Auto mode"
- "Participant Accounts"
- "Running"
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
| Opens EBP-06 · the BrokerWindow line | EBP-06 `to.EBP06()` | planned until EBP-06 is built |
| Opens EBP-05 · this participant’s distribution | EBP-05 `to.EBP05()` | planned until EBP-05 is built |
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
| Opens EBP-03 · eligibility testing | EBP-03 `to.EBP03()` | planned until EBP-03 is built |
| Opens EBP-04 · contributions & remittance | EBP-04 `to.EBP04()` | planned until EBP-04 is built |
| Opens EBP-07 · Form 5500 tie-out | EBP-07 `to.EBP07()` | planned until EBP-07 is built |
| Opens the source with the figure lit (SHL-08) | SHL-08 `to.SHL08()` | planned until SHL-08 is built |
| Opens EBP-09 · administrative expenses & compliance | EBP-09 `to.EBP09()` | planned until EBP-09 is built |
| Opens SHL-12 · sign off | SHL-12 `to.SHL12()` | planned until SHL-12 is built |
| Inbound | from AUD-12, AUD-27, EBP-05, EBP-09 | planned with each host |

## Acceptance
- EBP-08: every artboard above renders from its fixture scenario at Tier C (A-05 §5.4).
- Notes from the plan: Persona Marcus Delaney. L3 (HL) + L4 (MO); "Signed off" only after L4. Vesting covers the 6 participants terminated in 2025 (DF-34). **Tier-2 cut candidate** (chapter 01 §1.8.4)

## Deviations
| ID | What differs from the handoff | Why | Decision recorded |
|---|---|---|---|
| DV-EBP-08-1 | Agent-off path: every agent-filled value has a keyed or imported equivalent with a required citation note; the agent states read "not cleared" until A-04's `workpapers.drafting` and the firm's opt-in hold | A-05 F13; ADR-112 | DEC-1857 |

## Parity
| Artboard | Tier | Diff % | Notes |
|---|---|---|---|
| all | C | — | reported once the screen is built |

## Open gaps
None.
