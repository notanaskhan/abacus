# EBP-04 · Contributions & remittance timeliness

| Field | Value |
|---|---|
| Route and params | `/audits/$auditId/ebp/contributions` · `?tab=reconciliation\|timeliness\|testing`; `?ov=payroll:<id>` (deposit drawer) |
| Template and host frame | T6 grammar inside the T2 cockpit (rail 330 + canvas 1036) |
| Surface | firm (never a client surface) |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/EBP-04 Contributions & remittance timeliness/` (README.md, spec.md; no revision file) |
| Epic and tasks | A-05 · SPEC-640 · contract stub A-05-T04 (`docs/contracts/ebp-workpapers.md`) · bundle T05 · migrations T06 and later · seed T07 |
| Manifest status | planned |

## States
| Artboard | Viewer (persona) and clock | Snapshot | Data condition that produces it | Endpoints | Parity tier | Status |
|---|---|---|---|---|---|---|
| a · Late deposit found | a–e `hannah-leclerc` · Sep 24 10:15 AM; f · **Wed Sep 30, 2026 3:10 PM** | d: run state `running`; e: F-1 concluded, AJE-1 client-approved fixtures (C8/C18 shapes); f: correction event | late deposit found (default) | see API | C | live |
| b · Timeliness tab | a–e `hannah-leclerc` · Sep 24 10:15 AM; f · **Wed Sep 30, 2026 3:10 PM** | d: run state `running`; e: F-1 concluded, AJE-1 client-approved fixtures (C8/C18 shapes); f: correction event | Timeliness tab — the 26-row table written out by month with the same dates every 14 days from Jan 10 | see API | C | live |
| c · Testing tab | a–e `hannah-leclerc` · Sep 24 10:15 AM; f · **Wed Sep 30, 2026 3:10 PM** | d: run state `running`; e: F-1 concluded, AJE-1 client-approved fixtures (C8/C18 shapes); f: correction event | Testing tab — 25-participant deferral and match recalculation (AUD-12 variant b grammar) with rows 8 and 15 flagged → EBP-03 | see API | C | live |
| d · Agent running | a–e `hannah-leclerc` · Sep 24 10:15 AM; f · **Wed Sep 30, 2026 3:10 PM** | d: run state `running`; e: F-1 concluded, AJE-1 client-approved fixtures (C8/C18 shapes); f: correction event | agent running — tally pills "Pending", Card A rows skeleton, rail spinner "Running" | see API | C | live |
| e · Concluded | a–e `hannah-leclerc` · Sep 24 10:15 AM; f · **Wed Sep 30, 2026 3:10 PM** | d: run state `running`; e: F-1 concluded, AJE-1 client-approved fixtures (C8/C18 shapes); f: correction event | concluded — finding F-1 linked chip "Significant deficiency · concluded by MO" (from AUD-15) and AJE-1 "Client approved" | see API | C | live |
| f · Corrected | a–e `hannah-leclerc` · Sep 24 10:15 AM; f · **Wed Sep 30, 2026 3:10 PM** | d: run state `running`; e: F-1 concluded, AJE-1 client-approved fixtures (C8/C18 shapes); f: correction event | Corrected (render Wed 30 Sep 2026, 3:10 PM): card C reads lost earnings $64.38 deposited Sep 30, 2026 · correction green-tint "Corrected Sep 30 — VFCP Self-Correction Component" · SCC notice "to be filed with EBSA Oct 1" · Form 5330 "Not required — excise tax relieved under PTE 2002-51" · Schedule H line 4a "Yes · 33,540 · fully corrected under VFCP and PTE 2002-51" (4a preview: "Contributions pending correction… | see API | C | live |
| loading, error, not allowed, off | as above | — | the read never answers / 5xx / walled 404 / `ebp.modules` off: C-20 | — | C | live |

## API
| Method and path | Purpose | Action (agent) |
|---|---|---|
| `GET /ebp/contributions/reconciliation` · `GET /ebp/contributions/payrolls` · `GET /ebp/contributions/payrolls/{pid}` | Waterfall, timeliness, deposit drawer | `ebp.read` |
| `GET /ebp/late-remittances` · `GET /ebp/late-remittances/{id}` | The single object with formula provenance | `ebp.read` |
| `POST /ebp/late-remittances/{id}/corrections` `{lost_earnings_deposited_on, scc_notice_on, form_5330_status, evidence_version_ids}` | Record a correction (event) | `ebp.correction.record` (deny) — manager, senior |
| `GET /ebp/schedule-h/4a` · `POST /ebp/schedule-h/4a/draft` | Preview; hand to EBP-07 Schedules | `ebp.read` · `ebp.schedule.draft` (deny) |

Prefix `/v1/audits/{work_item_id}` unless the path starts with `/v1`. Sign-offs, notes, issues and decision cards are P-04's routes on EBP targets registered with `register_reviewable`.

## Status
Status words come from the generated `status.ts` (C2): the A-05 rows drafted for T05 (`ebp_provision`, `ebp_provider_check`, `ebp_test_result`, `ebp_late_remittance`, `ebp_certification_point`, `ebp_form5500_line`, `estimate`, `related_party`, `party_in_interest`) plus `audit_section`.

## Copy
Verbatim from the handoff (copy keys in `screens/EBP-04/copy.ts` when built). Key strings:
- "Contribution Reconciliation · Not started · Begin…"
- "Year-end contribution cutoff not resolved"
- "Contributions & remittance — Northwind 401(k)"
- "Audits"
- "All Audits"
- "PY2025 Employee Benefit Plan Audit"
- "BH Audit Methodology · EBP v3"
- "Fieldwork"
- "Sort by run"
- "Auto mode"
- "Contributions & Remittance"
- "In progress"
- "Planning ›"
- "5 of 6"
- "SOC 1 waiting on inputs"
- "Edit"
- "Sign off…"
- "Source Docs"
- "Reconciliation (on) · Timeliness · Testing"
- "Open in Excel"
- "Payroll → trust → financial statements"
- "pre-tax $746,600.00 · Roth $131,800.00 = W-3 Box 12 D / AA"
- "Proposed to client"
- "Remittance timeliness · 26 payrolls"

## Links
| From | To (manifest builder) | Planned or live |
|---|---|---|
| Opens AUD-01 · all audits | AUD-01 `to.AUD01()` | planned until AUD-01 is built |
| Opens SHL-12 | SHL-12 `to.SHL12()` | planned until SHL-12 is built |
| Opens AUD-03 · source documents | AUD-03 `to.AUD03()` | planned until AUD-03 is built |
| Opens AUD-15 · finding F-1 | AUD-15 `to.AUD15()` | planned until AUD-15 is built |
| Opens EBP-03 | EBP-03 `to.EBP03()` | planned until EBP-03 is built |
| Opens SHL-15 · then AUD-15 | SHL-15 `to.SHL15()` | planned until SHL-15 is built |
| Opens EBP-07 · Supplemental schedules | EBP-07 `to.EBP07()` | planned until EBP-07 is built |
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
| Opens EBP-05 · distributions & loans | EBP-05 `to.EBP05()` | planned until EBP-05 is built |
| Inbound | from AUD-08, AUD-11, AUD-15, AUD-17, AUD-27, EBP-02, EBP-03, EBP-05, EBP-06, EBP-07, EBP-08, EBP-09 | planned with each host |

## Acceptance
- EBP-04: every artboard above renders from its fixture scenario at Tier C (A-05 §5.4).
- Notes from the plan: Persona Hannah Leclerc. Owns the single `late_remittance`. State e reads F-1 (A-06, AUD-15) and AJE-1 "Client approved" (C8/C18); state f is a person's recorded correction, never time alone. Most-referenced screen in J03

## Deviations
| ID | What differs from the handoff | Why | Decision recorded |
|---|---|---|---|
| DV-EBP-04-1 | Agent-off path: every agent-filled value has a keyed or imported equivalent with a required citation note; the agent states read "not cleared" until A-04's `workpapers.drafting` and the firm's opt-in hold | A-05 F13; ADR-112 | DEC-1857 |

## Parity
| Artboard | Tier | Diff % | Notes |
|---|---|---|---|
| all | C | — | reported once the screen is built |

## Open gaps
None.
