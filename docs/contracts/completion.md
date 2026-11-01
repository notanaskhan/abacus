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
