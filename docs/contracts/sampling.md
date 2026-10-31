# Sampling API (internal; v1)

| Field | Value |
|---|---|
| Register row | internal sampling API (A-03 §8.1; not a numbered C-contract) in `docs/contracts/README.md` |
| Version | v1 |
| Status | stub (A-03-T02); live per route with A-03-T07, T10 and T13 |
| Provider epic | A-03 |
| Consumers | AUD-11, SHL-14 c, AUD-02 rail, AUD-03 "Sample-driven" band; A-05 (EBP-03/04/05), A-06 (`projection`), A-08 (MUS, AUD-12), K-03 (Sheet row source), A-11 (C17 tools) |
| Freeze sprint | S20 (the stub merges by Thu Jul 29, 2027) |
| Flag | `sampling.sample_sets` (default off; DEC-137 override, expires 2027-04-28) |
| Spec | `docs/specs/SPEC-580-a03-sampling-and-tb-mapping-s20.md` (AC-11, AC-12) |
| ADRs | ADR-340 (P-57), ADR-050, ADR-160, ADR-031 |

## 1. Purpose
Populations with completeness ties, sample sets with frozen, re-performable versions (seed,
sampler version, inputs and items hashes), their human approval, and the item-request fan-out.
Code computes every size, tie, stratum and draw (ADR-050); people start draws and approve them.

## 2. Who may call it
| Operation | Method and path | Matrix action | Roles allowed | Agent or system principal |
|---|---|---|---|---|
| Picker | `GET /v1/work-items/{wid}/sample-sets` | `sample_set.read` | engagement team, EQR, specialist | agent `task_scope`; system denied |
| Create set | `POST /v1/work-items/{wid}/sample-sets` | `sample_set.create` | EP, manager, senior | denied |
| Build population | `POST /v1/work-items/{wid}/populations` | `population.create` | EP, manager, senior, staff | denied |
| Population | `GET /v1/populations/{pid}` | `population.read` | engagement team | agent `task_scope` |
| Record a tie | `POST /v1/populations/{pid}/ties` | `population.create` | EP, manager, senior, staff | denied |
| Draw a version | `POST /v1/sample-sets/{sid}/versions` (202, `Idempotency-Key`) | `sample_set.create` | EP, manager, senior | denied |
| Projection | `GET /v1/sample-sets/{sid}?version=n` | `sample_set.read` | engagement team | agent `task_scope` |
| Draw progress | `GET /v1/sample-sets/{sid}/versions/{n}/draw` | `sample_set.read` | engagement team | agent `task_scope` |
| Items | `GET /v1/sample-sets/{sid}/versions/{n}/items?q=&cursor=` | `sample_set.read` | engagement team | agent `task_scope` |
| Approve | `POST /v1/sample-sets/{sid}/versions/{n}/approve` | `sample_set.approve` (`not_preparer_of_target`) | EP, manager | denied (DB CHECK `approved_actor_kind = 'human'`) |
| Export | `GET /v1/sample-sets/{sid}/versions/{n}/export.xlsx` | `sample_set.export` (`not_offshore`) | EP, manager, senior, staff | denied |
| Fan-out preview | `POST …/versions/{n}/item-requests/preview` | `sample_set.generate_requests` | EP, manager, senior | denied |
| Fan-out | `POST …/versions/{n}/item-requests` (`Idempotency-Key`) | `sample_set.generate_requests` | EP, manager, senior | denied |

Every client and third-party principal answers 404 (INV-4: they see only the item requests a
sample produces). Support sessions are denied every write.

## 3. Models
`backend/src/abacus/modules/sampling/contract.py`; every field carries a classification
(ADR-031). Population display fields, names, record keys, amounts and rationales are
`confidential`; ids, counts, hashes, seeds and statuses `internal`. Restricted columns (SSN, DOB,
bank account) are refused at parse (422 `restricted_column`) and never copied.

- `PopulationOut` (source facts, record count and unit, total, SHA-256, sampling unit, deviation
  definition, `CompletenessTieOut[]`), `PopulationIn` (`UploadSourceIn` | `GeneralLedgerSourceIn`,
  discriminated on `kind`), `TieIn`.
- `SampleSetOut` (version, status, population, `ParametersOut` with citations, `StratumOut[]`,
  items total and amount, `SampleSetVersionOut[]`, `inputs_hash`, `items_hash`, `content_hash`,
  `allowed_actions`), `SampleSetSummaryOut`, `SampleItemOut`, `DrawProgressOut`.
- `VersionIn` has **no seed field**: the server draws a 24-bit seed from `secrets`; only the
  scenario loader on a synthetic tenant passes `seed_source = scenario` (403 `seed_not_allowed`).
- `ApproveIn {seen_hash, acknowledge_override}`, `ItemRequestsIn`, `ItemRequestPreviewOut`,
  `ItemRequestsCreatedOut {created, by_surface, batch_id}`.

## 4. Status words
`sample_set_version` (drawing, draft, approved, superseded, failed) and `completeness_tie_result`
(tie, off, check), generated from `docs/product/status-vocabulary.yaml` into
`kernel/_statuses.py` and `packages/ui/src/status.gen.ts`.

## 5. Errors
`completeness_tie_required`, `population_not_tied`, `override_not_acknowledged`,
`content_changed`, `sample_not_approved` (409); `restricted_column`, `column_map_invalid`,
`citation_unverified`, `population_unreadable`, `duplicate_record_key` (422; A-03-T07, DEC-1660);
`seed_not_allowed`, `not_preparer_of_target` (403). Facts carry identifiers only
(`restricted_column` and `column_map_invalid` name the field: `record_key`, `name`, `date`,
`amount`).

## 6. Human-only actions and audit events
Human only: `sample_set.approve` (L2 through `review.api`), and every write in §2. Audit:
`population.created`, `population.tie_recorded`, `sample_set.created`, `sample_set.drawn` (seed,
sampler_version, method, size), `sample_set.override_requested`, `sample_set.override_approved`,
`sample_set.approved`, `sample_set.superseded`, `sample_set.exported`,
`sample_set.requests_generated`. Outbox: `sample_set.approved`, `population.created`.

## 7. Stub behaviour (A-03-T02; DEC-1553)
Client principal 404 → the action authorised (work-item routes on the work item's engagement;
population and sample-set routes at firm level with their read action until T05 gives them an
engagement, a non-person refused on a write) → 404 with the flag off → the Brightwater Hale
fixture for the fixture ids in `sampling/contract_fixtures.py` (Northwind Participants Version 2
and its census; Granite Peak's disbursements) → 501 `not_implemented` otherwise.

## 8. Module API
`sampling.api`: `attribute_size`, `udl`, `udl_percent`, `projected_misstatement`, `SAMPLER_VERSIONS`,
`SAMPLER_CURRENT` today; `population_view`, `sample_version_view`, `approved_items`, `draw` with
T07/T10.
