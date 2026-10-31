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
`content_changed`, `version_not_draft` (A-03-T10), `sample_not_approved` (409);
`restricted_column`, `column_map_invalid`, `citation_unverified`, `population_unreadable`,
`duplicate_record_key` (422; A-03-T07, DEC-1660); `override_not_below`, `parameters_invalid`,
`size_table_missing`, `size_exceeds_population` (422; A-03-T10, DEC-1662);
`seed_not_allowed`, `not_preparer_of_target` (403). Facts carry identifiers only
(`restricted_column` and `column_map_invalid` name the field: `record_key`, `name`, `date`,
`amount`).

## 6. Human-only actions and audit events
Human only: `sample_set.approve` (L2 through `review.api`), and every write in §2. Audit:
`population.created`, `population.tie_recorded`, `sample_set.created`, `sample_set.drawn` (seed,
sampler_version, method, size), `sample_set.override_requested`, `sample_set.override_approved`,
`sample_set.approved`, `sample_set.superseded`, `sample_set.exported`,
`sample_set.requests_generated`, and (A-03-T10) `sample_set.draw_completed`,
`sample_set.draw_failed`. The audit `Ref` carries identifiers, integers and hashes only, so
`sample_set.drawn` records the seed, size and inputs hash (the hash covers the method and the
sampler version). Outbox: `sample_set.approved`, `sample_set.approval_requested` (C16
`sample_set_approval_requested` to the engagement's partner and managers), `population.created`
(not yet emitted, DEC-1660).

## 7. Stub behaviour (A-03-T02; DEC-1553)
Client principal 404 → the action authorised (work-item routes on the work item's engagement;
population and sample-set routes at firm level with their read action until T05 gives them an
engagement, a non-person refused on a write) → 404 with the flag off → the Brightwater Hale
fixture for the fixture ids in `sampling/contract_fixtures.py` (Northwind Participants Version 2
and its census; Granite Peak's disbursements) → 501 `not_implemented` otherwise.

### 7.1 Live routes (A-03-T10; DEC-1662)
Every sample-set route but the item-request fan-out (T13) is live. A route keyed by a sample set
refuses a client (404) and a non-person write, checks the flag, then authorises its action on the
set's own engagement (walls 404, INV-3). The fixture ids still answer the fixture. The create route
answers `SampleSetCreatedOut` (the set has no version yet, so it is not a picker row); the picker
lists sets with at least one drawn version and shows each one's newest version that did not fail.
`POST …/versions` takes an `Idempotency-Key`: a replay answers the first version and draws
nothing. The draw runs in `SampleDrawWorkflow` (interactive queue); `…/draw` reports `drawing` until
it is `draft` (or `failed` with a code). Approval authorises `sample_set.approve` with the version's
preparers (who drew it and every L1 signer) on the resource, so a preparer gets 403
(`not_preparer_of_target`); then 409 `version_not_draft`, `content_changed`, `population_not_tied`,
`override_not_acknowledged`, in that order. Sign-off target type: `sample_set_version` (L1 the
preparer through `POST /v1/sign-offs`, L2 the approval); gate kind `sample_set_approval`.

## 8. Module API
`sampling.api`: `attribute_size`, `udl`, `udl_percent`, `projected_misstatement`, `SAMPLER_VERSIONS`,
`SAMPLER_CURRENT`; `population_view` (T07); `draw(ctx, sample_set_id, body, scenario_seed=)` (T10:
the scenario loader's seed on a synthetic firm only, 403 `seed_not_allowed` otherwise),
`section_state` and `AUDIT_SECTION` (the Fieldwork › Sample Selection rail row assurance
registers). `methodology.api.attribute_sample_size(tenant_id, rmm=, tolerable_rate=,
expected_rate=, confidence=, as_of=)` reads K-02's `attribute_sample_sizes` table (C21 part B).
`sample_version_view` and `approved_items` arrive with their first consumer (T13).
