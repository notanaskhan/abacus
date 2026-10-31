# EBP-06 · Investments, certification & trust tie-out

| Field | Value |
|---|---|
| Route and params | `/audits/$auditId/ebp/investments` · `?layer=unadjusted\|aje\|rje\|final` |
| Template and host frame | T2 with dock = Viewer |
| Surface | firm (never a client surface) |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/EBP-06 Investments, certification & trust tie-out/` (README.md, spec.md; no revision file) |
| Epic and tasks | A-05 · SPEC-640 · contract stub A-05-T04 (`docs/contracts/ebp-workpapers.md`) · bundle T05 · migrations T06 and later · seed T07 |
| Manifest status | planned |

## States
| Artboard | Viewer (persona) and clock | Snapshot | Data condition that produces it | Endpoints | Parity tier | Status |
|---|---|---|---|---|---|---|
| a · Prepared | a, b, d `ana-cruz` · Sep 24; c `ana-cruz` · **Mon Sep 14, 2026 9:24 AM (E0)**; e `hannah-leclerc` | b: `?layer=unadjusted`; c: certification unevaluated | prepared, Final layer (default) | see API | C | live |
| b · Unadjusted layer | a, b, d `ana-cruz` · Sep 24; c `ana-cruz` · **Mon Sep 14, 2026 9:24 AM (E0)**; e `hannah-leclerc` | b: `?layer=unadjusted`; c: certification unevaluated | Unadjusted layer — receivable row shows $0.00 and net assets $16,812,400.00 = trust | see API | C | live |
| c · Certification pending | a, b, d `ana-cruz` · Sep 24; c `ana-cruz` · **Mon Sep 14, 2026 9:24 AM (E0)**; e `hannah-leclerc` | b: `?layer=unadjusted`; c: certification unevaluated | certification pending (as of Sep 14) — certification card rows ring discs, amber banner 32h "Certified trust report uploaded – needs review. Sign-off is held until the certification is evaluated." | see API | C | live |
| d · Agent agreeing | a, b, d `ana-cruz` · Sep 24; c `ana-cruz` · **Mon Sep 14, 2026 9:24 AM (E0)**; e `hannah-leclerc` | b: `?layer=unadjusted`; c: certification unevaluated | agent agreeing — ✓ MS pills appear row by row (70ms), viewer row highlight follows | see API | C | live |
| e · Signed off | a, b, d `ana-cruz` · Sep 24; c `ana-cruz` · **Mon Sep 14, 2026 9:24 AM (E0)**; e `hannah-leclerc` | b: `?layer=unadjusted`; c: certification unevaluated | signed off — header chip "✓ HL", rail olive ✓ "Reviewed · HL" | see API | C | live |
| loading, error, not allowed, off | as above | — | the read never answers / 5xx / walled 404 / `ebp.modules` off: C-20 | — | C | live |

## API
| Method and path | Purpose | Action (agent) |
|---|---|---|
| `GET /ebp/investments?layer=unadjusted\ | aje\ | rje\ |
| `POST /ebp/trust-tb/adopt` `{evidence_version_id, lines, citation_ids}` | Calls `ledger.api.record_document_snapshot`; human adopter | `ledger.snapshot.create_from_document` (deny) — senior+ |
| `GET /ebp/certification` · `PUT /ebp/certification/points/{key}` `{answer, note}` | Evaluate a point (event) | `ebp.read` · `ebp.certification.evaluate` (deny) |

Prefix `/v1/audits/{work_item_id}` unless the path starts with `/v1`. Sign-offs, notes, issues and decision cards are P-04's routes on EBP targets registered with `register_reviewable`.

## Status
Status words come from the generated `status.ts` (C2): the A-05 rows drafted for T05 (`ebp_provision`, `ebp_provider_check`, `ebp_test_result`, `ebp_late_remittance`, `ebp_certification_point`, `ebp_form5500_line`, `estimate`, `related_party`, `party_in_interest`) plus `audit_section`.

## Copy
Verbatim from the handoff (copy keys in `screens/EBP-06/copy.ts` when built). Key strings:
- "complete and accurate"
- "Investments & certification — Northwind 401(k)"
- "Audits"
- "All Audits"
- "PY2025 Employee Benefit Plan Audit"
- "BH Audit Methodology · EBP v3"
- "Fieldwork"
- "Sort by run"
- "Auto mode"
- "Investments & Certification"
- "Prepared · AC"
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
- "Testing ⌄"
- "In progress · 2 exceptions"
- "In progress"

## Links
| From | To (manifest builder) | Planned or live |
|---|---|---|
| Opens AUD-01 · all audits | AUD-01 `to.AUD01()` | planned until AUD-01 is built |
| Opens AUD-03 · Trust / Recordkeeper Reports | AUD-03 `to.AUD03()` | planned until AUD-03 is built |
| Opens EBP-04 · AUD-16 later | EBP-04 `to.EBP04()` | planned until EBP-04 is built |
| Opens EBP-05 | EBP-05 `to.EBP05()` | planned until EBP-05 is built |
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
| Opens EBP-03 · eligibility testing | EBP-03 `to.EBP03()` | planned until EBP-03 is built |
| Opens EBP-07 · Form 5500 tie-out | EBP-07 `to.EBP07()` | planned until EBP-07 is built |
| Opens SHL-12 · sign off Investments & Certification | SHL-12 `to.SHL12()` | planned until SHL-12 is built |
| Opens SHL-08 · Harborline Summary of Net Trust Assets, row 1 | SHL-08 `to.SHL08()` | planned until SHL-08 is built |
| Inbound | from AUD-06, AUD-08, AUD-11, AUD-12, AUD-27, EBP-01, EBP-02, EBP-03, EBP-04, EBP-05, EBP-07, EBP-08, EBP-09 | planned with each host |

## Acceptance
- EBP-06: every artboard above renders from its fixture scenario at Tier C (A-05 §5.4).
- Notes from the plan: Personas Ana Cruz (a–d), Hannah Leclerc (e). Layers from C9/C8 (AJE, RJE, Final answer `layer_unavailable` until A-06 registers its adjustment source). Plan TB from the trust report via ADR P-58. Notes receivable below investments, not certified (ASU 2010-25)

## Deviations
| ID | What differs from the handoff | Why | Decision recorded |
|---|---|---|---|
| DV-EBP-06-1 | Agent-off path: every agent-filled value has a keyed or imported equivalent with a required citation note; the agent states read "not cleared" until A-04's `workpapers.drafting` and the firm's opt-in hold | A-05 F13; ADR-112 | DEC-1857 |

## Parity
| Artboard | Tier | Diff % | Notes |
|---|---|---|---|
| all | C | — | reported once the screen is built |

## Open gaps
None.
