# EBP-05 · Distributions & participant loans

| Field | Value |
|---|---|
| Route and params | `/audits/$auditId/ebp/distributions` · `?tab=loans\|distributions`; `?ov=participant:<key>` |
| Template and host frame | T6 grammar inside the T2 cockpit |
| Surface | firm (never a client surface) |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/EBP-05 Distributions & participant loans/` (README.md, spec.md; no revision file) |
| Epic and tasks | A-05 · SPEC-640 · contract stub A-05-T04 (`docs/contracts/ebp-workpapers.md`) · bundle T05 · migrations T06 and later · seed T07 |
| Manifest status | planned |

## States
| Artboard | Viewer (persona) and clock | Snapshot | Data condition that produces it | Endpoints | Parity tier | Status |
|---|---|---|---|---|---|---|
| a · Loans | a–e `hannah-leclerc` · Sep 24 (d 9:52 AM) | c: fixture-only PY comparative off 3,200 | Loans, agent draft ready (default) | see API | C | live |
| b · Distributions | a–e `hannah-leclerc` · Sep 24 (d 9:52 AM) | c: fixture-only PY comparative off 3,200 | Distributions tab | see API | C | live |
| c · Exception variant | a–e `hannah-leclerc` · Sep 24 (d 9:52 AM) | c: fixture-only PY comparative off 3,200 | exception variant — "Prior-period comparative does not agree": beginning balance shows amber "off 3,200" against PY audited FS $291,700.00 and a Raise exception prompt (illustrative; not in the seed default) | see API | C | fixture-only (illustrative) |
| d · Adopted | a–e `hannah-leclerc` · Sep 24 (d 9:52 AM) | c: fixture-only PY comparative off 3,200 | adopted — "✓ AC" chips replace outlined ticks; rail "Prepared · AC" | see API | C | live |
| e · Signed off | a–e `hannah-leclerc` · Sep 24 (d 9:52 AM) | c: fixture-only PY comparative off 3,200 | signed off — "✓ HL" | see API | C | live |
| loading, error, not allowed, off | as above | — | the read never answers / 5xx / walled 404 / `ebp.modules` off: C-20 | — | C | live |

## API
| Method and path | Purpose | Action (agent) |
|---|---|---|
| `GET /ebp/loans/rollforward` · `GET /ebp/loans/new` · `GET /ebp/loans/offsets` · `GET /ebp/participants/{pid}/loan` | EBP-05 loans and drawer | `ebp.read` |

Prefix `/v1/audits/{work_item_id}` unless the path starts with `/v1`. Sign-offs, notes, issues and decision cards are P-04's routes on EBP targets registered with `register_reviewable`.

## Status
Status words come from the generated `status.ts` (C2): the A-05 rows drafted for T05 (`ebp_provision`, `ebp_provider_check`, `ebp_test_result`, `ebp_late_remittance`, `ebp_certification_point`, `ebp_form5500_line`, `estimate`, `related_party`, `party_in_interest`) plus `audit_section`.

## Copy
Verbatim from the handoff (copy keys in `screens/EBP-05/copy.ts` when built). Key strings:
- "Defaulted participant loans of terminated participants"
- "Prior-period participant loan comparative does not agree"
- "Distributions & loans — Northwind 401(k)"
- "Audits"
- "All Audits"
- "PY2025 Employee Benefit Plan Audit"
- "BH Audit Methodology · EBP v3"
- "Fieldwork"
- "Sort by run"
- "Auto mode"
- "Distributions & Loans"
- "Complete · Sep 23, 4:18 PM"
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

## Links
| From | To (manifest builder) | Planned or live |
|---|---|---|
| Opens the Keystone loan report at this row (SHL-08) | SHL-08 `to.SHL08()` | planned until SHL-08 is built |
| Opens EBP-07 · Schedule H line 2e(1) | EBP-07 `to.EBP07()` | planned until EBP-07 is built |
| Opens SHL-12 · sign off as preparer (L1) | SHL-12 `to.SHL12()` | planned until SHL-12 is built |
| Opens SHL-15 · the exception routes to AUD-15 | SHL-15 `to.SHL15()` | planned until SHL-15 is built |
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
| Opens EBP-08 · participant accounts | EBP-08 `to.EBP08()` | planned until EBP-08 is built |
| Inbound | from AUD-06, AUD-08, AUD-11, AUD-12, AUD-27, EBP-02, EBP-03, EBP-04, EBP-06, EBP-07, EBP-08, EBP-09 | planned with each host |

## Acceptance
- EBP-05: every artboard above renders from its fixture scenario at Tier C (A-05 §5.4).
- Notes from the plan: Persona Hannah Leclerc. Second sample set `0x7B13C4` (A-03). Offsets are distributions (2e(1)), never "deemed distributions"; 2g = 0; Part IV 4b = No

## Deviations
| ID | What differs from the handoff | Why | Decision recorded |
|---|---|---|---|
| DV-EBP-05-1 | Agent-off path: every agent-filled value has a keyed or imported equivalent with a required citation note; the agent states read "not cleared" until A-04's `workpapers.drafting` and the firm's opt-in hold | A-05 F13; ADR-112 | DEC-1857 |
| DV-EBP-05-2 | State c is illustrative: fixture-only; real data reaches it, the seed default does not | The README marks it illustrative | DEC-1857 |

## Parity
| Artboard | Tier | Diff % | Notes |
|---|---|---|---|
| all | C | — | reported once the screen is built |

## Open gaps
None.
