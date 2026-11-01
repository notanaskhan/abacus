# EBP-03 · Eligibility testing

| Field | Value |
|---|---|
| Route and params | `/audits/$auditId/ebp/eligibility` · `?item=<sampleItemId>`; `?dock=viewer`; `?ov=request` (SHL-14) |
| Template and host frame | T2 with dock = Viewer (rail 330 + canvas 536 + viewer 490) |
| Surface | firm (never a client surface) |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/EBP-03 Eligibility testing/` (README.md, spec.md; no revision file) |
| Epic and tasks | A-05 · SPEC-640 · contract stub A-05-T04 (`docs/contracts/ebp-workpapers.md`) · bundle T05 · migrations T06 and later · seed T07 |
| Manifest status | planned |

## States
| Artboard | Viewer (persona) and clock | Snapshot | Data condition that produces it | Endpoints | Parity tier | Status |
|---|---|---|---|---|---|---|
| a · Agent-tested | a–d `ana-cruz`, e `hannah-leclerc` · Sep 24 10:15 AM | b: `never()` on the results handler + scripted progressive rows; c: row 22 open | agent-tested, 2 exceptions (default) | see API | C | live |
| b · Agent testing | a–d `ana-cruz`, e `hannah-leclerc` · Sep 24 10:15 AM | b: `never()` on the results handler + scripted progressive rows; c: row 22 open | agent testing — rows fill top to bottom with 70ms stagger, Result cells show 15px spinners, viewer swaps documents as each row completes | see API | C | live |
| c · Needs human | a–d `ana-cruz`, e `hannah-leclerc` · Sep 24 10:15 AM | b: `never()` on the results handler + scripted progressive rows; c: row 22 open | needs human — row 22 amber "Needs human" until Ana marks the hire-date difference as no effect | see API | C | live |
| d · Adopted | a–d `ana-cruz`, e `hannah-leclerc` · Sep 24 10:15 AM | b: `never()` on the results handler + scripted progressive rows; c: row 22 open | adopted — header chip "✓ AC" and rail sub-line "Prepared · AC" | see API | C | live |
| e · Signed off | a–d `ana-cruz`, e `hannah-leclerc` · Sep 24 10:15 AM | b: `never()` on the results handler + scripted progressive rows; c: row 22 open | signed — "✓ HL" chip, rail olive ✓ "Reviewed · HL" | see API | C | live |
| loading, error, not allowed, off | as above | — | the read never answers / 5xx / walled 404 / `ebp.modules` off: C-20 | — | C | live |

## API
| Method and path | Purpose | Action (agent) |
|---|---|---|
| `GET /ebp/participants?q=&cursor=` | Masked participants | `ebp.read` (task_scope, tokens only) |
| `POST /ebp/participants/{pid}/reveals` `{field: ssn\ | dob, reason}` | Logged reveal, 30 s, `no-store` |
| `POST /tests` `{variant, sample_set_id}` · `GET /tests/{tid}` · `GET /tests/{tid}/items/{iid}` | Shared attribute grid (workpapers) | `test.create` (deny) · `ebp.read` |
| `PUT /tests/{tid}/items/{iid}/results/{attr}` `{result, note}` | Human pass, exception or no effect | `test.mark` (deny) |
| `POST /tests/{tid}/run` | Begin… for a grid variant | `agent_run.start` |
| `GET /ebp/eligibility` · `POST /ebp/population-queries` `{rule}` | Header cards, matrices; code population query | `ebp.read` · `ebp.population_query.run` (task_scope) |
| `GET /ebp/loans/rollforward` · `GET /ebp/loans/new` · `GET /ebp/loans/offsets` · `GET /ebp/participants/{pid}/loan` | EBP-05 loans and drawer | `ebp.read` |

Prefix `/v1/audits/{work_item_id}` unless the path starts with `/v1`. Sign-offs, notes, issues and decision cards are P-04's routes on EBP targets registered with `register_reviewable`.

## Status
Status words come from the generated `status.ts` (C2): the A-05 rows drafted for T05 (`ebp_provision`, `ebp_provider_check`, `ebp_test_result`, `ebp_late_remittance`, `ebp_certification_point`, `ebp_form5500_line`, `estimate`, `related_party`, `party_in_interest`) plus `audit_section`.

## Copy
Verbatim from the handoff (copy keys in `screens/EBP-03/copy.ts` when built). Key strings:
- "Eligibility testing — Northwind 401(k)"
- "Audits"
- "All Audits"
- "PY2025 Employee Benefit Plan Audit"
- "BH Audit Methodology · EBP v3"
- "Fieldwork"
- "Sort by run"
- "Auto mode"
- "Eligibility Testing"
- "In progress · 2 exceptions"
- "Planning ›"
- "5 of 6"
- "SOC 1 waiting on inputs"
- "Edit"
- "Sign off…"
- "Source Docs"
- "Auto-Enrollment Provisions"
- "Auto-Escalation Provisions"
- "Dual-Source Data Verification Matrix"
- "No effect: entry 02/01/2025 either way"
- "Eligibility Testing Matrix"
- "Exception"
- ".
Card "
- " Buttons: tonal "

## Links
| From | To (manifest builder) | Planned or live |
|---|---|---|
| Opens AUD-01 · all audits | AUD-01 `to.AUD01()` | planned until AUD-01 is built |
| Opens SHL-12 | SHL-12 `to.SHL12()` | planned until SHL-12 is built |
| Opens AUD-03 · source documents | AUD-03 `to.AUD03()` | planned until AUD-03 is built |
| Opens the provision in EBP-02 | EBP-02 `to.EBP02()` | planned until EBP-02 is built |
| Opens the draft finding in AUD-15 | AUD-15 `to.AUD15()` | planned until AUD-15 is built |
| Opens SHL-15 | SHL-15 `to.SHL15()` | planned until SHL-15 is built |
| Opens SHL-14 · sent to POR-03 | SHL-14 `to.SHL14()` | planned until SHL-14 is built |
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
| Opens EBP-04 · contributions & remittance | EBP-04 `to.EBP04()` | planned until EBP-04 is built |
| Opens EBP-05 · distributions & loans | EBP-05 `to.EBP05()` | planned until EBP-05 is built |
| Opens EBP-07 · Form 5500 tie-out | EBP-07 `to.EBP07()` | planned until EBP-07 is built |
| Inbound | from AUD-11, AUD-12, AUD-27, EBP-02, EBP-04, EBP-05, EBP-06, EBP-07, EBP-08, EBP-09 | planned with each host |

## Acceptance
- EBP-03: every artboard above renders from its fixture scenario at Tier C (A-05 §5.4).
- Notes from the plan: Personas Ana Cruz (a–d), Hannah Leclerc (e). Viewer is an HR record, never a USCIS Form I-9 (spec wins over the catalogue). Exceptions use Flag + pill, never a row colour

## Deviations
| ID | What differs from the handoff | Why | Decision recorded |
|---|---|---|---|
| DV-EBP-03-1 | Agent-off path: every agent-filled value has a keyed or imported equivalent with a required citation note; the agent states read "not cleared" until A-04's `workpapers.drafting` and the firm's opt-in hold | A-05 F13; ADR-112 | DEC-1857 |

## Parity
| Artboard | Tier | Diff % | Notes |
|---|---|---|---|
| all | C | — | reported once the screen is built |

## Open gaps
None.
