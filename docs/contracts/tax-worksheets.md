# WS-1 · Tax worksheets, K-1 treatments and residency

| Field | Value |
|---|---|
| Version | v1 |
| Status | **final (T-04-T50, S39; DEC-4528)**: worksheets, fields, formulas and their review are served; additive changes only |
| Provider epic | T-04 (SPEC-649) |
| Consumers | TXI-01, TXI-02, TXI-03; TAX-05's Worksheets tab |
| Flag | `tax.individual_workpapers` (T-04-T09) |
| Code | `backend/src/abacus/modules/tax/workspace_contract.py` |

## Who may call it
| Operation | Method and path | Action |
|---|---|---|
| Worksheet tree | `GET /v1/tax/returns/{id}/worksheets` | `return_worksheet.read` |
| Worksheet fields | `GET /v1/tax/worksheets/{id}/fields?q=` | `return_worksheet.read` |
| K-1 activities | `GET /v1/tax/returns/{id}/k1-activities`, `GET /v1/tax/k1-activities/{id}` | `k1_treatment.read` |
| Propose treatments (202 run) | `POST /v1/tax/k1-activities/{id}/treatment-runs` | `k1_treatment.resolve` |
| Override a treatment (reason required) | `POST /v1/tax/k1-treatments/{id}/override` | `k1_treatment.override` |
| Residency | `GET /v1/tax/returns/{id}/residency` | `residency.read` |
| Ask for the residency proposal (202 run) | `POST /v1/tax/returns/{id}/residency/proposal-runs` | `residency.request_proposal` |
| State allocation | `GET /v1/tax/returns/{id}/state-allocation` | `residency.read` |
A section carries `section_id` (T-04-T29, additive), the `return_worksheet_section` sign-off target
for SHL-12. Field edits are P-04's `PUT /v1/fields/return_worksheet/…`; approving treatments and confirming
residency go through P-04's proposals, whose appliers also authorise `k1_treatment.approve` and
`residency.confirm`.

## Status words
`return_field_view`, `k1_activity`, `k1_treatment` (with "Changed vs {year}"),
`residency_determination` (C2, T-04-T04).

## Human-only actions
`k1_treatment.approve`, `k1_treatment.override`, `residency.confirm`, `residency.request_proposal`.

## Audit events
`k1_treatment.approved`, `k1_treatment.overridden`, `residency.confirmed` (with the build rows).
Values are TRI (`restricted`): no value reaches an audit row (DEC-60).


## Adding a worksheet form (T-04-T50)
1. Add the form's worksheet definition (fields, derivations `input`, `formula`, `copy` or
   `engine`) to the worksheet registry and its parameters to `compute/individual/parameters/`
   (PROTECTED, the CPA's review).
2. Formula fields use the closed grammar (ADR-237); an `engine` field is the engine of record's
   and is never proposed or exported back (DEC-77).
3. Register its review facts with `register_reviewable_facts` and its fields with
   `register_field_owner` (as `worksheet_review.register` does); goldens pin every figure.
