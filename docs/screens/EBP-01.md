# EBP-01 · Plan profile & service providers

| Field | Value |
|---|---|
| Route and params | `/audits/$auditId/ebp/plan` · `?edit=1`; `?ov=provider:<id>` (O2 drawer); `?ov=invite:<providerId>` (POR-14 invite sheet) |
| Template and host frame | T2 record cockpit without dock (rail 330 + canvas 1036) |
| Surface | firm (never a client surface) |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/EBP-01 Plan profile & service providers/` (README.md, spec.md; no revision file) |
| Epic and tasks | A-05 · SPEC-640 · contract stub A-05-T04 (`docs/contracts/ebp-workpapers.md`) · bundle T05 · migrations T06 and later · seed T07 |
| Manifest status | planned |

## States
| Artboard | Viewer (persona) and clock | Snapshot | Data condition that produces it | Endpoints | Parity tier | Status |
|---|---|---|---|---|---|---|
| a · Complete | a–d `marcus-delaney` · Thu Sep 24, 2026 10:15 AM CT | b: `plan_number` null; c: Summit draft Schedule C extracted; d: `?edit=1` | complete (default) | see API | C | live |
| b · Missing PN | a–d `marcus-delaney` · Thu Sep 24, 2026 10:15 AM CT | b: `plan_number` null; c: Summit draft Schedule C extracted; d: `?edit=1` | missing PN — "Plan number (PN)" value ink-4 "—" with brick Flag and red-ink helper "Form 5500 needs a three-digit PN (001–499). The recordkeeper ID 58217 is not a plan number." | see API | C | live |
| c · Provider mismatch | a–d `marcus-delaney` · Thu Sep 24, 2026 10:15 AM CT | b: `plan_number` null; c: Summit draft Schedule C extracted; d: `?edit=1` | provider mismatch — Keystone row amber TriangleAlert "Summit's draft Schedule C lists Keystone Retirement Svcs LLC, EIN ending 4402; the Keystone service agreement shows EIN ending 4420" with "Raise exception…" (the fix belongs to Summit, the 5500 preparer, so the Summit row shows a muted "Correction requested" note) | see API | C | live |
| d · Edit mode | a–d `marcus-delaney` · Thu Sep 24, 2026 10:15 AM CT | b: `plan_number` null; c: Summit draft Schedule C extracted; d: `?edit=1` | edit mode — values become #EFEEEB fields with focus ring, sticky "Save" primary in the header | see API | C | live |
| loading, error, not allowed, off | as above | — | the read never answers / 5xx / walled 404 / `ebp.modules` off: C-20 | — | C | live |

## API
| Method and path | Purpose | Action (agent) |
|---|---|---|
| `GET /ebp/plan` | Plan facts, computed status card (filer status, due dates, independence read from P-07), provider checks | `ebp.read` (task_scope) |
| `PATCH /ebp/plan` `{fields, citation_note, seen_version}` | Human edit through `review.api.record_value`; PN through `organisations.api` | `ebp.plan.edit` (deny) — EP, manager, senior |
| `GET /ebp/providers` · `POST /ebp/providers` · `PATCH /ebp/providers/{pid}` · `GET /ebp/providers/{pid}` | Providers, drawer (contacts, documents, request history) | `ebp.read` · `ebp.provider.manage` (deny) |
| `POST /ebp/providers/{pid}/invite` `{contact}` | C5 delegation to a named person, scope `request_item` | `ebp.provider.invite` (deny) |
| `POST /ebp/plan-reviews` `{document_version_ids[]}` | Start an `ebp_provisions` run; new workpaper version | `agent_run.start` (n/a) + A-04's `workpapers.drafting` gate |
| `GET /ebp/plan-reviews/current?version=` | Provisions, conflicts, amendment tags, diff vs previous | `ebp.read` (task_scope) |
| `GET /ebp/plan-expenses` · `GET /ebp/erisa-budget-account` · `GET /ebp/compliance-tests` · `GET /ebp/plan-qualification` · `POST /ebp/plan-expenses/{id}/request-support` | EBP-09; support → SHL-14 prefill | `ebp.read` · `ebp.provider.request` (deny) |

Prefix `/v1/audits/{work_item_id}` unless the path starts with `/v1`. Sign-offs, notes, issues and decision cards are P-04's routes on EBP targets registered with `register_reviewable`.

## Status
Status words come from the generated `status.ts` (C2): the A-05 rows drafted for T05 (`ebp_provision`, `ebp_provider_check`, `ebp_test_result`, `ebp_late_remittance`, `ebp_certification_point`, `ebp_form5500_line`, `estimate`, `related_party`, `party_in_interest`) plus `audit_section`.

## Copy
Verbatim from the handoff (copy keys in `screens/EBP-01/copy.ts` when built). Key strings:
- "Plan profile & service providers — Northwind 401(k)"
- "Audits"
- "All Audits"
- "PY2025 Employee Benefit Plan Audit"
- "BH Audit Methodology · EBP v3"
- "Fieldwork"
- "Sort by run"
- "Auto mode"
- "Overview"
- "Northwind Robotics 401(k) Plan"
- "PY2025 · Northwind Robotics, Inc."
- "Overview ⌄"
- "PN 001 · §103(a)(3)(C)"
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
| Opens POR-14 · scoped to delegated requests | POR-14 `to.POR14()` | planned until POR-14 is built |
| Opens SIG-01 · Form 5558 filing record | SIG-01 `to.SIG01()` | planned until SIG-01 is built |
| Opens SHL-15 · the fix belongs to Summit, the 5500 preparer | SHL-15 `to.SHL15()` | planned until SHL-15 is built |
| Opens AUD-10 | AUD-10 `to.AUD10()` | planned until AUD-10 is built |
| Opens SHL-14 · request composer | SHL-14 `to.SHL14()` | planned until SHL-14 is built |
| Opens CLI-02 · client record | CLI-02 `to.CLI02()` | planned until CLI-02 is built |
| Opens KNW-03 · program editor | KNW-03 `to.KNW03()` | planned until KNW-03 is built |
| Opens AUD-29 · activity log | AUD-29 `to.AUD29()` | planned until AUD-29 is built |
| Opens AUD-06 · trial balance | AUD-06 `to.AUD06()` | planned until AUD-06 is built |
| Opens AUD-07 · materiality | AUD-07 `to.AUD07()` | planned until AUD-07 is built |
| Opens AUD-08 · risk assessment | AUD-08 `to.AUD08()` | planned until AUD-08 is built |
| Opens AUD-04 · audit program | AUD-04 `to.AUD04()` | planned until AUD-04 is built |
| Opens AUD-09 · internal control | AUD-09 `to.AUD09()` | planned until AUD-09 is built |
| Opens EBP-02 · plan provisions review | EBP-02 `to.EBP02()` | planned until EBP-02 is built |
| Opens AUD-11 · sample selection | AUD-11 `to.AUD11()` | planned until AUD-11 is built |
| Opens EBP-06 · investments & certification | EBP-06 `to.EBP06()` | planned until EBP-06 is built |
| Opens SHL-08 · adoption agreement · plan name | SHL-08 `to.SHL08()` | planned until SHL-08 is built |
| Opens ENG-05 · independence confirmations | ENG-05 `to.ENG05()` | planned until ENG-05 is built |
| Inbound | from AUD-11, AUD-12, AUD-27, EBP-02, EBP-03, EBP-04, EBP-05, EBP-06, EBP-07, EBP-08, EBP-09 | planned with each host |

## Acceptance
- EBP-01: every artboard above renders from its fixture scenario at Tier C (A-05 §5.4).
- Notes from the plan: Persona Marcus Delaney. PN on `client_entities.plan_number` (F-03/P-07); plan-year facts in `ebp_plans`. SOC link → AUD-10 (A-04; manual SOC type and period if tier-2 cut defers AUD-10). "Extended · Oct 15" → SIG-01 filing record link; Independence → ENG-05 (P-07). Never the competitor's "82150"

## Deviations
| ID | What differs from the handoff | Why | Decision recorded |
|---|---|---|---|
| DV-EBP-01-1 | Agent-off path: every agent-filled value has a keyed or imported equivalent with a required citation note; the agent states read "not cleared" until A-04's `workpapers.drafting` and the firm's opt-in hold | A-05 F13; ADR-112 | DEC-1857 |

## Parity
| Artboard | Tier | Diff % | Notes |
|---|---|---|---|
| all | C | — | reported once the screen is built |

## Open gaps
None.
