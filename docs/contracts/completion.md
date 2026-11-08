# Completion family v1 — findings, deficiencies, misstatements, SUM

| Field | Value |
|---|---|
| Owner | assurance (A-06; SPEC-642) |
| Status | stub (A-06-T05, 2026-11-01; DEC-1965); live per route with A-06-T09 to T13 |
| Code | `backend/src/abacus/modules/assurance/findings_contract.py` |
| Tests | `backend/tests/contracts/a06_completion/` (A-06-T06) |
| Flag | `assurance.completion` (default off; DEC-137, expires 2027-04-30) |
| Consumers | AUD-15 (findings), AUD-16 a, e, f (SUM), HOME-02 (decision rows), A-07 (the SUM snapshot for the representation letter; the AU-C 265 letter's deficiencies) |

## Rules
- A finding is a 1:1 extension of a P-04 issue (DEC-83); an agent's finding lands Proposed with
  every citation verified by C4 (`uncited_change` otherwise, INV-2) and reads "‹person› via Agent".
- Severity and the SUM conclusion are the engagement partner's C3 cards (`deficiency_severity`,
  `sum_conclusion`), decided with a rationale and a fresh second factor; the database refuses a
  Concluded deficiency without the person's decision on its own card (0644).
- Every figure is code's: projections from `sampling.compute`, the SUM from
  `assurance/compute/sum.py` (rollover, iron curtain, percents of PM and overall, the bar's ticks).
- Passing a misstatement on SUM is the EP's act with a reason (DF-28).

## Operations
| Operation | Method and path | Action |
|---|---|---|
| Findings | `GET /v1/work-items/{wi}/findings` | `finding.read` |
| Record a finding | `POST /v1/work-items/{wi}/findings` | `finding.create` |
| A finding | `GET /v1/findings/{id}` | `finding.read` |
| Convert | `POST /v1/findings/{id}/convert-to-deficiency` · `/convert-to-misstatement` | `finding.convert` |
| Resolve | `POST /v1/findings/{id}/resolve` | `finding.resolve` |
| Request the partner's decision | `POST /v1/findings/{id}/request-decision` | `finding.request_decision` |
| Misstatements | `GET /v1/work-items/{wi}/misstatements?view=` | `misstatement.read` |
| Pass on SUM | `POST /v1/misstatements/{id}/pass-to-sum` | `misstatement.pass_to_sum` |
| SUM | `GET /v1/work-items/{wi}/sum` | `sum.read` |
| A qualitative factor | `PUT /v1/work-items/{wi}/sum/qualitative-factors/{factor}` | `sum.update_factors` |
| Request the conclusion | `POST /v1/work-items/{wi}/sum/request-conclusion` | `sum.request_conclusion` |
| Snapshot | `POST /v1/work-items/{wi}/sum/snapshots` | `sum.snapshot` |

Every operation answers 404 to a client principal, 404 with the flag off and 501
`not_implemented` until its task.

## Statements v1 (A-06-T19, 2026-11-03, DEC-2209)
Stub behind `reporting.fs_disclosure` (404 off, 501 on until A-06-T25). Module:
`reporting/statements_contract.py`. Tables: migration 0660, DEC-80's canonical model.

| Operation | Method and path | Action |
|---|---|---|
| Current version tree with tie counts · code's draft (202) | `GET /v1/engagements/{id}/financial-statements` · `POST …/draft` | `statement.read` · `statement.draft` |
| A line's verified sources | `GET /v1/statement-versions/{id}/line-items/{line_id}/lineage` | `statement.read` |
| Tie-out run (202) and result | `POST /v1/statement-versions/{id}/tie-out` · `GET …/tie-out` | `statement.tie_out` · `statement.read` |
| Disclosure checklist: read · answer · adopt · review · export | `GET /v1/statement-documents/{id}/disclosure-checklist` · `PUT …/items/{key}` · `POST …/items/{key}/adopt` · `POST …/items:review` · `GET …/export.xlsx` | `disclosure_checklist.read/answer/review/export` |
| Send the DRAFT to the client (C10 deliverable + C18 `fs_draft`) | `POST /v1/statement-versions/{id}/send-draft` | `statement.send_draft` |
| Record management's approval (record mode) | `POST /v1/statement-versions/{id}/management-approval:record` | `statement.record_management_approval` |
| Template import (dry run first) · publish | `POST /v1/methodology/disclosure-checklists:import` · `POST …/{id}/versions/{v}/publish` | `disclosure_checklist_template.import` · `.publish` |
| Note templates: import (dry run first) · publish (A-06-T25, DEC-2389) | `POST /v1/methodology/statement-note-templates:import` · `POST …/{id}/versions/{v}/publish` | `statement_note_template.import` · `statement_note_template.publish` |

- **Database rules.**
  - A value whose source is `override` or `stale_override` needs `override_reason`.
  - An `na` answer needs its `reason`.
  - Versions, lines, values, tie-outs and approvals are insert-only (`statement_rows_immutable`).
  - An approval row is the session's own human actor.
  - A record-mode management approval needs its evidence.
- **Sends and approvals.** Sending a draft and recording management's approval are a person's
  acts (agent deny). Client approval is R-02's C18, never these routes.

## Screen contracts and consumer notes (A-06-T38)
AUD-15, AUD-16, AUD-17 and AUD-20: `docs/screens/AUD-15.md`, `AUD-16.md`, `AUD-17.md`, `AUD-20.md`, each with its artboards, deviations and consumer notes for A-05, A-07, R-02, C-02, T-05, A-09, A-10 and P-10.
