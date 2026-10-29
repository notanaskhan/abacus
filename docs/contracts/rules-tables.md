# Rules tables (C21 v1)

| Field | Value |
|---|---|
| Register row | C21 (`docs/contracts/README.md`) |
| Version | v1 |
| Status | stub (K-02-T02, 2026-10-29): every route 501 behind its flag; module APIs raise `NotImplementedError` |
| Provider epic | K-02 |
| Consumers | T-01 (8879 form set and Pub 1345 tolerances), T-02 (due dates; BH-TAX-02), T-03, T-08, A-04 (materiality), A-05 (5500/5558), A-06 (C8 `classify_entry`), C-01 (AJE, variance, SSARS), C-02 (1099 thresholds), P-04 (review levels), Q-05 (retention minimums), K-01 KNW-02d (standards sets) |
| Freeze sprint | S17 (Fri Jun 25, 2027 in the plan's calendar); additive changes in place, a breaking change ships as v2 with one sprint of overlap |
| Flags | `rules.reference_sets` (part A over HTTP); `knowledge.firm_standards` (part B over HTTP). Neither gates the Python module APIs: consumers gate with their own flags |
| Spec | SPEC-500; `docs/plan/epics/K-02.md` §4 |
| ADRs | ADR-300 (P-62 reference-data split), ADR-005 (people decide), ADR-050 (code computes), DEC-36, DEC-38, DEC-43, DEC-53, DEC-71, DEC-85 |

## 1. Purpose
Two kinds of versioned, effective-dated rules, both database rows changed by import, never by a commit. **Part A** (platform): global reference sets of public law and the `practice` calendar engine over them. **Part B** (methodology): per-tenant firm standards and threshold policies, each owned and published by a named partner, and the deterministic functions consumers call to apply them. Nothing here calls a model (INV-1).

## 2. Who may call it
| Operation | Method and path | Matrix action | Flag | Lands |
|---|---|---|---|---|
| Sets by kind | `GET /v1/reference-sets?kind=` → `ListPage[ReferenceSetOut]` | `reference_set.read` | `rules.reference_sets` | K-02-T05 |
| Resolve on a date | `GET /v1/reference-sets/{key}?as_of=` → `ReferenceSetResolvedOut` | `reference_set.read` | `rules.reference_sets` | K-02-T05 |
| A set's versions | `GET /v1/reference-sets/{key}/versions` → `ListPage[ReferenceSetVersionOut]` | `reference_set.read` | `rules.reference_sets` | K-02-T05 |
| Due dates | `GET /v1/due-dates?form=&tax_year=&period_end=&jurisdiction=&state=&county=` → `DueDateOut` | `due_date.read` | `rules.reference_sets` | K-02-T07 |
| Standards | `GET /v1/standards?kind=` → `ListPage[StandardOut]` | `firm_standard.read` | `knowledge.firm_standards` | K-02-T08 |
| Create | `POST /v1/standards` `StandardCreateIn` (fresh MFA) | `firm_standard.create` | `knowledge.firm_standards` | K-02-T08 |
| Detail | `GET /v1/standards/{id}?version=` → `StandardDetailOut` | `firm_standard.read` | `knowledge.firm_standards` | K-02-T08 |
| Assign owner | `PUT /v1/standards/{id}/owner` `StandardOwnerIn` | `firm_standard.assign_owner` | `knowledge.firm_standards` | K-02-T08 |
| A version | `GET /v1/standards/{id}/versions/{v}` (draft: partners only, else 404) | `firm_standard.read` | `knowledge.firm_standards` | K-02-T08 |
| New version | `POST /v1/standards/{id}/versions` (409 `draft_exists`) | `firm_standard.draft` (`owner_of_target`) | `knowledge.firm_standards` | K-02-T08 |
| Edit draft | `PATCH /v1/standards/{id}/versions/{v}` (If-Match; 409 `stale_version`, `not_draft`; 422 `payload_invalid`) | `firm_standard.draft` | `knowledge.firm_standards` | K-02-T08 |
| Discard draft | `DELETE /v1/standards/{id}/versions/{v}` (If-Match; status `discarded`, row kept) | `firm_standard.draft` | `knowledge.firm_standards` | K-02-T08 |
| Publish | `POST /v1/standards/{id}/versions/{v}/publish` `StandardPublishIn` (If-Match, Idempotency-Key, fresh MFA; 422 `effective_from_backdated`, `effective_from_not_after_current`) | **`firm_standard.publish`** (`owner_of_target`; human only) | `knowledge.firm_standards` | K-02-T08 |
| Diff | `GET /v1/standards/{id}/versions/{v}/diff?against=` → `StandardVersionDiffOut` | `firm_standard.read` | `knowledge.firm_standards` | K-02-T08 |
| Examples | `GET /v1/standards/{id}/examples?period=` → `StandardExamplesOut` | `firm_standard.read` | `knowledge.firm_standards` | K-02-T08 |
| Import | `POST /v1/standards/{id}/imports`, `POST /v1/standards/imports` `StandardImportIn` → `StandardImportResultOut` (422 `import_invalid`) | `firm_standard.import` | `knowledge.firm_standards` | K-02-T11 |
| Export | `GET /v1/standards/{id}/versions/{v}/export.xlsx` | `firm_standard.read` | `knowledge.firm_standards` | K-02-T11 |

Every route answers 404 to a client principal (INV-4) before anything else. There are **no reference-set write routes**: the operator CLI (K-02-T06) runs owner-only definer functions until PLT-01 (G-04). A non-owner partner's draft or publish is 403 `not_standard_owner`.

## 3. Models
Payloads are discriminated by `kind`, `payload_schema_version` 1 (`platform/reference_sets_contract.py`, `methodology/standards_contract.py`):
- **Reference kinds:** `due_date_rules`, `legal_holidays`, `disaster_postponements`, `form_8879_set` (rows plus `Pub1345Tolerances`), `information_return_thresholds`, `retention_minimums`, `standards_sets` (`family ∈ gaas_nonissuer · ssars · sqms`; no PCAOB or issuer set, a code never removed or re-familied). Reserved: `state_breach_matrix`, `state_retention_rules` (Q-05).
- **Standard kinds:** `review_checklist`, `review_levels`, `return_approval_policy`, `ssars_cas_settings` (table `firm_standards`); `aje_thresholds`, `variance_thresholds`, `materiality_ranges`, `document_confidence` (table `threshold_policies`).
- Classification: reference payloads `public`; standard payloads `internal`; example rows and BH-TAX-02 applies-to `confidential`. No TRI.

**Additive since the stub (K-02-T13, DEC-1154):** `StandardOut.entries`, `StandardVersionSummaryOut.tax_year`, `StandardDetailOut.labels` (ids to names, `visible()`-filtered), `StandardExamplesOut.caption`, `StandardExampleRowOut.approver_name` and `.cells`.

## 4. Status words
`reference_set_version`: draft · published · superseded (computed) · withdrawn. `firm_standard_version`: draft · published · superseded (computed) · discarded (hidden). Superseded is never stored: a later published version is effective on or before `as_of`. On the wire the derived code is not an enum value (the registry's derived codes stay out of OpenAPI): a summary is `published` with `current: false`, and the screen words it Superseded.

## 5. Module APIs (frozen with v1)
- `platform.api`: `reference_value(key, as_of)`, `form_8879_for(return_type, tax_year, jurisdiction, *, as_of)`, `pub1345_tolerances(tax_year, *, as_of)`, `information_return_threshold(form, payment_year)`, `retention_minimum(record_type, service_line)`.
- `practice.api`: `due_dates_for(form, tax_year, period_end, jurisdiction="US", location=None, event_date=None)`, `add_business_days(start, n, jurisdiction="US")`, `clock_due(kind, start)`.
- `methodology.api`: `current_version(tenant_id, standard_key, as_of)`, `classify_entry`, `variance_exceeded`, `materiality_range_for`, `validate_materiality`, `confidence_hold`, `required_review_levels`, `return_approval_policy`, `ssars_framework_for`, `register_standard_examples(kind, provider)`.

Every result carries the version id it used (INV-2). **`as_of` per consumer:** AJE classification, the entry's creation date; materiality validation, the decision date; checklists, `applies_to.tax_year`; BH-TAX-02, pinned on the return at creation; due dates, the period end. Consumers store the version id.

## 6. Human-only actions
`firm_standard.create`, `.assign_owner`, `.draft`, `.import`, `.publish`: agent, system and client principals denied; `firm_standard_versions.published_actor_kind = 'human'` is a database CHECK (K-02-T04). Reference sets: two-person publish (approver differs from drafter), a database CHECK (K-02-T03).

## 7. Audit and outbox events
Audit: `firm_standard.created`, `firm_standard.owner_changed`, `firm_standard_version.drafted / edited / imported / discarded / published`, the `threshold_policy_version.*` equivalents, `decision.refused_non_human`, `reference_set.published` / `.withdrawn` (system actor `operator:<drafter>`, approver in facts, per tenant). Outbox: `firm_standard.published`, `threshold_policy.published`, `reference_set.published`. Notification (C16): `reference_set.updated` "Rules table updated: {title} v{n}" to firm admins and tax partners (K-02-T12).

## 8. Consumer contract tests
T-01: `backend/tests/contracts/c21_t01/`; T-02: `backend/tests/contracts/c21_t02/`; both import the models and module-API signatures above and run in K-02's CI.
