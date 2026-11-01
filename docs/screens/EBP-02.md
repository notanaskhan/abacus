# EBP-02 · Plan provisions review

| Field | Value |
|---|---|
| Route and params | `/audits/$auditId/ebp/provisions` · `?version=1` (b2 snapshot); `?dock=viewer&doc=<evidenceVersionId>`; `?ov=issue` (SHL-15), `?ov=signoff` (SHL-12) |
| Template and host frame | T3 two-pane variant inside the cockpit (rail 330 + workpaper 536 + viewer 490) |
| Surface | firm (never a client surface) |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/EBP-02 Plan provisions review/` (README.md, spec.md; no revision file) |
| Epic and tasks | A-05 · SPEC-640 · contract stub A-05-T04 (`docs/contracts/ebp-workpapers.md`) · bundle T05 · migrations T06 and later · seed T07 |
| Manifest status | planned |

## States
| Artboard | Viewer (persona) and clock | Snapshot | Data condition that produces it | Endpoints | Parity tier | Status |
|---|---|---|---|---|---|---|
| a · Verified | a–e, b2 `hannah-leclerc` · Sep 24 10:15 AM | b: run finished, 0 of 20; b2: `?version=1`; e: L2 Sep 17 | verified (default) | see API | C | live |
| b · Agent draft | a–e, b2 `hannah-leclerc` · Sep 24 10:15 AM | b: run finished, 0 of 20; b2: `?version=1`; e: L2 Sep 17 | unverified — agent draft: ticks outlined ink-4 (◌), header "0 of 20 verified", micro pill "Agent draft"; Version 1 view shows 18 rows (Version 1 was read from the pre-2024-amendment adoption agreement, so the Long-term part-time and Catch-up rows that the 2024 amendment governs are absent) | see API | C | live |
| b2 · Version 1 snapshot | a–e, b2 `hannah-leclerc` · Sep 24 10:15 AM | b: run finished, 0 of 20; b2: `?version=1`; e: L2 Sep 17 | Version 1 snapshot | see API | C | live |
| c · SPD conflict | a–e, b2 `hannah-leclerc` · Sep 24 10:15 AM | b: run finished, 0 of 20; b2: `?version=1`; e: L2 Sep 17 | conflict SPD vs plan — Entry dates row amber TriangleAlert, value "First of month following" with an amber 18h pill "SPD: quarterly"; viewer switches to "Summary Plan Description 2025, p. 6" with the line "Entry dates: the first day of each calendar quarter" lit; action "Raise exception…" | see API | C | live |
| d · Amendment flag | a–e, b2 `hannah-leclerc` · Sep 24 10:15 AM | b: run finished, 0 of 20; b2: `?version=1`; e: L2 Sep 17 | mid-year amendment flag — Catch-up row tag "Amended Jan 1, 2025" | see API | C | live |
| e · Signed off | a–e, b2 `hannah-leclerc` · Sep 24 10:15 AM | b: run finished, 0 of 20; b2: `?version=1`; e: L2 Sep 17 | signed off — chip "✓ HL", Sign off button replaced by "Reviewed · HL Sep 17" ink-3 | see API | C | live |
| loading, error, not allowed, off | as above | — | the read never answers / 5xx / walled 404 / `ebp.modules` off: C-20 | — | C | live |

## API
| Method and path | Purpose | Action (agent) |
|---|---|---|
| `POST /ebp/plan-reviews` `{document_version_ids[]}` | Start an `ebp_provisions` run; new workpaper version | `agent_run.start` (n/a) + A-04's `workpapers.drafting` gate |
| `GET /ebp/plan-reviews/current?version=` | Provisions, conflicts, amendment tags, diff vs previous | `ebp.read` (task_scope) |
| `POST /v1/fields/ebp_provision/{id}/value/ticks` `{level: L1}` | Verify a provision (P-04 route) | `field.sign_off` (deny) |
| `POST /ebp/imports` `{evidence_version_id, kind, column_map}` · `GET /ebp/imports/{id}` | Code import with footing and completeness ties | `ebp.import.create` (deny) — senior, staff |

Prefix `/v1/audits/{work_item_id}` unless the path starts with `/v1`. Sign-offs, notes, issues and decision cards are P-04's routes on EBP targets registered with `register_reviewable`.

## Status
Status words come from the generated `status.ts` (C2): the A-05 rows drafted for T05 (`ebp_provision`, `ebp_provider_check`, `ebp_test_result`, `ebp_late_remittance`, `ebp_certification_point`, `ebp_form5500_line`, `estimate`, `related_party`, `party_in_interest`) plus `audit_section`.

## Copy
Verbatim from the handoff (copy keys in `screens/EBP-02/copy.ts` when built). Key strings:
- "Plan provisions review — Northwind 401(k)"
- "Audits"
- "All Audits"
- "PY2025 Employee Benefit Plan Audit"
- "BH Audit Methodology · EBP v3"
- "Fieldwork"
- "Sort by run"
- "Auto mode"
- "Plan Review (Version 2)"
- "Planning ›"
- "5 of 6"
- "SOC 1 waiting on inputs"
- "Reviewed · HL"
- "Sep 15, 2026 10:02 AM"
- "Sep 15, 2026 4:40 PM"
- "Prepared · AC"
- "In progress · 2 exceptions"
- "In progress"
- "Complete · Sep 23, 4:18 PM"
- "Not started"
- "Complete · 9:58 AM"
- "Plan Review"
- "Version 2"
- "✓ HL"

## Links
| From | To (manifest builder) | Planned or live |
|---|---|---|
| Opens AUD-01 · all audits | AUD-01 `to.AUD01()` | planned until AUD-01 is built |
| Opens AUD-03 · source documents | AUD-03 `to.AUD03()` | planned until AUD-03 is built |
| Opens SHL-15 · then AUD-15 Findings | SHL-15 `to.SHL15()` | planned until SHL-15 is built |
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
| Opens AUD-11 · sample selection | AUD-11 `to.AUD11()` | planned until AUD-11 is built |
| Opens EBP-06 · investments & certification | EBP-06 `to.EBP06()` | planned until EBP-06 is built |
| Opens EBP-03 · eligibility testing | EBP-03 `to.EBP03()` | planned until EBP-03 is built |
| Opens EBP-04 · contributions & remittance | EBP-04 `to.EBP04()` | planned until EBP-04 is built |
| Opens EBP-05 · distributions & loans | EBP-05 `to.EBP05()` | planned until EBP-05 is built |
| Opens EBP-07 · Form 5500 tie-out | EBP-07 `to.EBP07()` | planned until EBP-07 is built |
| Opens SHL-12 · sign off Plan Review | SHL-12 `to.SHL12()` | planned until SHL-12 is built |
| Inbound | from AUD-11, AUD-12, AUD-27, EBP-01, EBP-03, EBP-04, EBP-05, EBP-06, EBP-07, EBP-08, EBP-09 | planned with each host |

## Acceptance
- EBP-02: every artboard above renders from its fixture scenario at Tier C (A-05 §5.4).
- Notes from the plan: Persona Hannah Leclerc. Ticks are C3 `field_tick` sign-offs (L1) on `ebp_provision` targets; establishes the 536 + 490 MatchProvider grammar reused by EBP-03/06/07. Domain checks: §410(a)(4) entry, age 21 and 3 months, QACA 6% → 15% cap, match 3.5% max, 2-year QACA vesting; "Citations (20)" = row count

## Deviations
| ID | What differs from the handoff | Why | Decision recorded |
|---|---|---|---|
| DV-EBP-02-1 | Agent-off path: every agent-filled value has a keyed or imported equivalent with a required citation note; the agent states read "not cleared" until A-04's `workpapers.drafting` and the firm's opt-in hold | A-05 F13; ADR-112 | DEC-1857 |
| DV-EBP-02-2 | b2 (Version 1 snapshot) is a README deviation: 18 rows, before the 2024 amendment | README deviations list | DEC-1857 |

## Parity
| Artboard | Tier | Diff % | Notes |
|---|---|---|---|
| all | C | — | reported once the screen is built |

## Open gaps
None.
