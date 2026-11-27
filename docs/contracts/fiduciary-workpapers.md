# Fiduciary workpapers · FW-1 (v1)

> **T-06-T69 (DEC-6024):** the routes answer 404 without the firm's `tax_returns` entitlement, which replaced `tax.fiduciary_workpapers` and `tax.fiduciary_k1_release`.

| Field | Value |
|---|---|
| Version | v1 |
| Status | **stub** (T-07-T05, 2026-11-14); every route answers 501 behind its flag until its build task; additive after the S45 freeze (T-07 §8.2) |
| Provider epic | T-07 (SPEC-656) |
| Consumers | TXT-01, TXT-02, TXT-03 (T-07 FE rows); T-06 (TAX-11 previews, CLI-03 trust edges), T-08 (TAX-15 planning, TAX-16 amendments), W-02/W-03 (read-only instrument tools), I-02 (gate kinds in the Today brief) |
| Flags | `tax.fiduciary_workpapers` (TXT-01, TXT-02), `tax.fiduciary_k1_release` (TXT-03); the reader's exposure is the AI-policy stage, not a flag |
| Code | `backend/src/abacus/modules/tax/fiduciary_contract.py` |
| Matrix | T-07-T03's rows in `docs/architecture/permission-matrix/tax.yaml` |

## 1. Who may call it
Every route answers, in order: a client principal 404; the flag off for the firm 404; the route's
one matrix action (walls first, 404: INV-3); then 501 until its build task. Every write is a
person's (`agent: deny`, INV-1). Paths sit under the tax module's `/v1/tax` prefix (the epic's
`/v1/tax-returns/{id}` reads `/v1/tax/returns/{return_id}`, as every tax route does).

## 2. Routes

| Method · path | Action | Response | Build task |
|---|---|---|---|
| `GET /v1/tax/returns/{return_id}/instrument` | `instrument.read` | `InstrumentOut` (profile, instrument, segmentation, interpretation, determinations, cited-by, reader, `allowed_actions`) | T12 |
| `POST /v1/tax/returns/{return_id}/instrument` (Idempotency-Key) | `instrument.attach` | `InstrumentOut` | T12 |
| `GET /v1/tax/governing-instruments/{instrument_id}/clauses` | `instrument.read` | `InstrumentClausesOut` | T12 |
| `POST /v1/tax/governing-instruments/{instrument_id}/clauses` | `instrument.attach` | `InstrumentClauseOut` (manual marking) | T12 |
| `POST /v1/tax/returns/{return_id}/instrument/read` (Idempotency-Key) | `instrument.read_run` | 202 `ReaderRunAcceptedOut`; 409 `consent_required`, `capability_unavailable`, `not_segmented` | T13 |
| `POST /v1/tax/returns/{return_id}/instrument/determinations` | `instrument_determination.edit` | `InstrumentDeterminationOut`; 422 `uncited_change` | T12 |
| `PATCH /v1/tax/instrument-determinations/{determination_id}` | `instrument_determination.edit` | `InstrumentDeterminationOut`; 422 `uncited_change`; 409 `version_conflict`, `interpretation_locked` | T12 |
| `POST /v1/tax/instrument-interpretations/{interpretation_id}/reopen` | `instrument_interpretation.reopen` | `InstrumentInterpretationOut` | T12 |
| `GET /v1/tax/returns/{return_id}/instrument/cited-by` | `instrument.read` | `[InstrumentCitedByOut]` | T12 |
| `GET /v1/tax/returns/{return_id}/fiduciary-computation?view=tree\|character&version=` | `fiduciary_computation.read` | `FiduciaryComputationOut`; 409 `interpretation_not_approved` | T16 |
| `POST /v1/tax/returns/{return_id}/fiduciary-computation/recompute` (Idempotency-Key) | `fiduciary_computation.recompute` | `FiduciaryRecomputeOut` (idempotent by `inputs_hash`) | T16 |
| `GET /v1/tax/returns/{return_id}/fiduciary-computation.xlsx?version=` | `fiduciary_computation.export` | deterministic XLSX | T16 |
| `GET\|POST /v1/tax/returns/{return_id}/fai-lines`, `POST …/fai-lines/import-from-statement`, `PATCH /v1/tax/fai-lines/{line_id}` | `fiduciary_computation.read` / `fai_line.edit` | `FaiLinesOut`, `FaiLineOut` | T16 |
| `GET\|POST /v1/tax/returns/{return_id}/trust-expenses`, `PATCH /v1/tax/trust-expenses/{expense_id}` | `fiduciary_computation.read` / `fai_line.edit` | `TrustExpensesOut`, `TrustExpenseOut` | T16 |
| `GET\|POST /v1/tax/returns/{return_id}/trust-distributions`, `PATCH /v1/tax/trust-distributions/{distribution_id}` | `fiduciary_computation.read` / `trust_distribution.edit` | `TrustDistributionsOut`, `TrustDistributionOut` | T16 |
| `GET /v1/tax/returns/{return_id}/beneficiaries` | `beneficiary_allocation.read` | `BeneficiariesOut` | T23 |
| `PUT /v1/tax/client-entities/{client_entity_id}/sixty-five-day-elections/{tax_year}` | `fiduciary_election.record` | `SixtyFiveDayElectionOut` (inserts a row) | T23 |
| `POST /v1/tax/returns/{return_id}/trustee-questions` | `fiduciary_election.read` | `TrusteeQuestionDraftOut` (a C5 draft; C5 `request_item.send` sends) | T23 |

Reused, not repeated: P-04's `POST /v1/sign-offs` (L1 and L3 on `instrument_interpretation`, L2
on `fai_dni_computation`), T-02's K-1 package prepare, release and resend routes (the 1041 gate
answers 409 `gate_unmet {final_approval, form_8879_f}`, T-07-T24), C6 v2 run events for reader
progress.

## 3. Shapes and rules
- **No instrument text** leaves through FW-1 (AC-15.3): `InstrumentClauseOut` carries `label`,
  `heading`, `ordinal`, pages, `regions` and `text_sha256`. The reader face re-reads the sealed
  layer through `evidence.api.text_layer`'s masked projection. Clause citations are C4's
  `instrument_clause` kind (ADR-343): locator `{instrument_id, segmentation_id, clause_id,
  quote_sha256}`.
- **Classification:** figures, determination values and dates of payment are TRI (`restricted`,
  §7216); names are Confidential; the EIN is the last four only.
- **Figures are code's** (ADR-050): `FiduciaryComputationOut` carries every node value, share, tally
  and the by-character table, with `engine_version`, `inputs_hash` and `parameter_set`. Changed rows
  carry `prior_value` against the last signed version (DEC-84); the browser never sums.
- **Determination keys:** `grantor_status`, `trust_type`, `fai_definition`, `trustee_fees`,
  `principal_invaded` need ≥ 1 clause citation (422 `uncited_change`); `exemption` and
  `election_65_day` may be clause-free.
- **Edits** carry `expected_version` (409 `version_conflict`) and a reason; approved determinations
  answer 409 `interpretation_locked` until a manager reopens.
- **Footing fixtures** for consumers: `backend/tests/contracts/fiduciary/fixtures/calloway_2025.json`
  (FAI 430,000 − fees 30,000 = DNI 400,000; IDD 240,000; boxes 60,000 / 180,000 / 144,000).
