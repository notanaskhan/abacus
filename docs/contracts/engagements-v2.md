# Engagements family · ENG-01, ENG-02 and ENG-03 (v2; C1 v1.1 note)

| Field | Value |
|---|---|
| Register row | Screen-family contracts in `docs/contracts/README.md`; an additive C1 v1.1 note to `work-items.md` (P-07 §8.1) |
| Version | v2 of the engagement surfaces (C1 stays v1; these are additive operations and models) |
| Status | index, record, gates and recorded letter live (P-07-T15, 2026-10-24); catalogue and drafts stub until P-07-T16 |
| Provider epic | P-07 (`engagements`) |
| Consumers | ENG-01, ENG-02, ENG-03 (P-07-T20, T21, T27, T28); CLI-02's Engagements tab; fixtures P-07-T11; A-01 (AUD-02 hangs off ENG-02 and its gates); N-02 (`acceptance_decided_at`, the G3 swap); T-02 and C-01 (tax and CAS through ENG-03) |
| Freeze sprint | the sprint review after the stub (P-07 §8.1) |
| Flag | `engagements.v2` (default off, created 2026-10-23, expires 2027-04-21 under DEC-137's override) |
| Spec | `docs/specs/SPEC-321-clients-engagements-v2.md` (outline, Story 3) |
| ADRs | ADR-139 (P-36), ADR-140 (P-39), ADR-005, ADR-031; P-04 (gate service), P-26 (recorded letter until C7); DEC-19, DEC-38, DEC-39, DEC-43, DEC-63, DEC-132, DEC-137, DEC-143 |

## 1. Purpose
Consumers can rely on an engagements index on the P-36 envelope whose status tiles (`counts`, minus the selected tile) and service-line segments (`facets.service_line`) come from one grouped query over the same `visible()` predicate and sum to `total`; a record projection with rail bands, contacts, letter summary, gates, tab counts and a read-only reason; the gates on their own; an interim recorded letter that enforces the G1 date rule; a selectable engagement-type catalogue that never contains single audit; and wizard drafts with per-step validation, "Start acceptance" and a one-unit-of-work create.

**Stub behaviour.** With `engagements.v2` off every route below answers 404. With it on, the index, record, gates and recorded letter are live (P-07-T15, DEC-224); the catalogue, drafts, start-acceptance and create answer 501 `not_implemented` until P-07-T16. No fixtures yet (P-07-T11).

**Beside the live routes, not replacing them.** `GET /v1/engagements` (a plain `EngagementSummaryOut` list), `GET /v1/engagements/{id}` (C1's `EngagementOut`), `PUT /v1/engagements/{id}/letter` (SPEC-025's letter step), `POST /v1/engagements` and the team routes keep their paths and shapes. The v2 index is served at `/v1/engagements/index` and the record at `/v1/engagements/{id}/record`; P-07-T15 moves them to the plain paths when the v1 consumers are gone (a v1 to v2 change with one sprint of overlap, recorded in §10). `/index` is matched before the live `/{engagement_id}` because `engagements.api.ROUTERS` lists the v2 routers first; `test_ac14_the_v2_index_is_matched_before_the_live_record_route` holds that order. `PUT …/letter/record` becomes the interim recorded-letter route; the SPEC-025 `PUT …/letter` stays as an adapter until P-07-T59.

## 2. Who may call it
Matrix: `docs/architecture/permission-matrix/engagements.yaml` and `organisations.yaml` (`client.intake`).

| Operation | Method and path | Matrix action | Roles allowed | Agent or system principal |
|---|---|---|---|---|
| Engagements index (ENG-01) | `GET /v1/engagements/index?service_line=&status=&tile=&office_id=&partner_id=&letter=&next_due=&period=&client_id=&q=&cursor=&limit=` | `engagement.read_metadata` (existing) | every engagement team role, practice leader `in_scope`, quality partner, firm admin (metadata), `client_service`, platform support (SPEC-012) | denied (no cell) |
| Record projection (ENG-02) | `GET /v1/engagements/{engagement_id}/record` | `engagement.read_metadata`; content bands need `engagement.read` | as the index | denied |
| Gates | `GET /v1/engagements/{engagement_id}/gates` | `engagement.read_metadata` | as the index | denied |
| Record signed letter | `PUT /v1/engagements/{engagement_id}/letter/record` | `letter.record` (existing) | engagement partner, manager; `gates_met(G1)` when live (DEC-143); the "Not required this year" exception by the EP only (the service checks) | **denied** |
| Type catalogue (ENG-03 step 1) | `GET /v1/engagement-types` | `engagement.create` (existing) | firm admin, practice leader today; DEC-38's partner, manager and seniors-by-setting with P-07-T16 | **denied** |
| Create a draft | `POST /v1/engagement-drafts` | `engagement.create` | as the catalogue; own drafts only (OQ-17) | **denied** |
| Read a draft | `GET /v1/engagement-drafts/{draft_id}` | `engagement.create` | the draft's owner | **denied** |
| Autosave | `PATCH /v1/engagement-drafts/{draft_id}` | `engagement.create` | the owner | **denied** |
| Discard | `DELETE /v1/engagement-drafts/{draft_id}` | `engagement.create` | the owner | **denied** |
| Validate a step | `POST /v1/engagement-drafts/{draft_id}/validate` | `engagement.create` | the owner | **denied** |
| Start acceptance (ENG-03 d) | `POST /v1/engagement-drafts/{draft_id}/start-acceptance` | `client.intake` (new, OQ-2) | firm admin, partner (`firm_partner`); manager when live (DEC-143) | **denied** |
| Create (ENG-03) | `POST /v1/engagement-drafts/{draft_id}/create` + `Idempotency-Key` | `engagement.create` | as the catalogue | **denied** |

Client roles hold no write action here. They do hold `engagement.read_metadata` for their own engagement (SPEC-020), but the v2 index, record and gates are firm surfaces: P-07-T15 answers a client principal 404, as ENG-01 and ENG-02's contracts say (agent and client principals deny).

## 3. Models
Code: `backend/src/abacus/modules/engagements/contract.py`. Tags: **C** confidential, **I** internal, **P** public.

- **`EngagementIndexPage`** = the P-36 envelope of `EngagementIndexRowOut` + `summary` I (`EngagementIndexSummaryOut`: `prospect`, `awaiting_letter`, `past_due`, the ENG-01 summary line). `counts` per `EngagementStatus` code minus the selected `tile` (`declined` never shows); `facets.service_line` the segments. No `hidden_by_wall` field.
- **`EngagementIndexRowOut`**: `id` I, `name` C, `client_id` I, `client_name` C, `client_entity_id` I, `type` I (C1's 14 `EngagementType` codes), `service_line` I, `status` I (`EngagementStatus`), `period_label` C, `fiscal_period_start` C, `fiscal_period_end` C, `office_id` I, `office_name` I, `partner_user_id` I, `partner_initials` I, `work_items` C (`EngagementWorkItemLineOut`: `id`, `kind`, `label` C, `pill_object`, `pill_code`), `letter` I (`EngagementLetterSummaryOut`), `next_due` C (`EngagementNextDueOut`: `on`, `tone` `past_due`/`soon`/`normal`, `label` C), `allowed_actions` I.
- **`EngagementLetterSummaryOut`**: `status` I (`LetterRecordStatus`: `not_signed`, `signed`), `signed_on` I, `last_event` I (`sent`, `viewed`), `last_event_on` I, `signed_count` I, `signer_count` I, `not_required_this_year` I.
- **`EngagementRecordOut`**: subbar facts (`id`, `name` C, `client_id`, `client_name` C, `client_entity_id`, `client_entity_name` C, `type`, `service_line`, `status`, `period_label` C, `fiscal_period_start/end` C), `bands` C (`EngagementRailBandOut`: `band` `details`/`review_delivery`/`client_portal`, `rows` of `EngagementRailRowOut` `key`, `text` C, `user_id`, `on`, `pill_object`, `pill_code`), `contacts` C (`EngagementDesignationOut`: `designation`, `contact_id`, `name` C), `letter` I, `gates` I, `tab_counts` I (`work_items`, `team`), `read_only_reason` I (`archived`), `version` I, `allowed_actions` I.
- **`EngagementGateOut`** (C1 v1.1): `gate` I (`G1` to `G9`), `met` I, `blockers` I (`GateBlockerRefOut`: `type`, `id`, `reason_code`), `met_at` I, `met_by_user_id` I. Met, blocked (blockers) or not started (neither). C1's `GateOut` (`G1` to `G3`, string blockers) stays on `EngagementOut`.
- **`LetterRecordIn`**: `mode` I (`signed`, `not_required_this_year`), `client_signed_on` I, `firm_signed_on` I, `client_signer_contact_id` I, `firm_signer_user_id` I, `signed_copy_version_id` I (stored write-once through `evidence` first), `not_required_reason` C (1–1000). **`EngagementLetterRecordOut`**: the same facts plus `engagement_id`, `status` (`LetterRecordStatus`), `acceptance_decided_at` (the G1 decision), `recorded_by`, `recorded_at`, `engagement_status` (`contracted` once G3 is met).
- **`EngagementTypeCatalogueOut`**: `items` of **`EngagementTypeEntryOut`**: `code` I (18 catalogue codes: `form_1040`, `form_1041`, `form_1065`, `form_1120s`, `form_1120`, `form_990`, `forms_706_709`, `notice_response`; `ebp_audit`, `fs_audit`, `review`, `compilation`, `preparation`, `agreed_upon_procedures`, `soc1`, `soc2`; `cas_monthly_close`, `advisory`), `engagement_type` I, `family` I (`tax`, `audit_assurance`, `cas_advisory`), `work_item_kind` I, `label` P, `standard_line` P, `availability` I (`available`, `needs_entitlement`), `entitlement` I (`attest`, `group_audit`), `group_audit_allowed` I, `steps` I (`EngagementTypeStepOut`: `step`, `field_codes`). **No `single_audit` code or entry.**
- **`EngagementDraftIn`**: `client_id` I, `client_entity_id` I, `type_code` I (a code string, so an unknown or excluded code is the server's 422 `unknown_engagement_type`), `step` I, `payload` C. **`EngagementDraftPatchIn`**: `seen_version` I (required) and the same fields, absent = unchanged. **`EngagementDraftPayload`**: identifiers and typed values only, no TIN, no free text beyond `name` (`name` C, `methodology_version_id`, `standards_code`, `scope_code`, `fiscal_period_start/end` C, `period_label` C, `deadlines` `[{code, on}]`, `team` `[{user_id, role}]`, `eqr_user_id`, `group_audit`, `portal_contact_ids`, `prior_engagement_id`).
- **`EngagementDraftOut`**: `id`, `created_by`, `client_id`, `client_entity_id`, `type_code` (`CatalogueTypeCode`), `step`, `payload` C, `prospect_engagement_id`, `gates`, `version`, `saved_at` ("Draft · saved 9:39 AM"), `allowed_actions`.
- **`DraftValidateIn`** `{step}` → **`EngagementDraftValidationOut`**: `draft_id`, `step`, `valid`, `problems` (`DraftProblemOut`: `field`, `code`), `gates`.
- **`EngagementDraftDiscardedOut`**: `draft_id`, `discarded_at`. **`AcceptanceStartedOut`**: `draft_id`, `engagement_id`, `acceptance_record_id`, `engagement_status` (`prospect`).
- **`DraftCreateIn`** `{confirm_duplicate}` → **`EngagementFromDraftOut`**: `engagement_id`, `engagement_status` (`accepted`), `work_item_ids`, `independence_requested_user_ids`, `methodology_version_id`.

## 4. Status words
`engagement`: `prospect` Prospect · `accepted` Accepted · `contracted` Letter signed · `active` Active · `on_hold` On hold · `delivered` Delivered · `archived` Archived (`declined` is never a tile). `letter_record`: `not_signed` Not signed · `signed` Signed. Work-item sub-lines name their own objects' codes. Gates read met, blocked or not started (derived, not a status field).

## 5. Human-only actions
`engagement.create`, `client.intake` and `letter.record` deny `agent` and `system` at the matrix (I-AGENT-NEVER, P-07 §4.4). Agent and system principals have no role on a firm resource, and the live create and letter routes also require a live human. The agent never creates an engagement (a draft through a manifest later).

## 6. Errors
| Status | Body | When |
|---|---|---|
| 404 | `{"detail": "not found"}` | `engagements.v2` off; a walled or unknown engagement; someone else's draft |
| 501 | `{"detail": "not_implemented"}` | the flag on, before the implementing task |
| 409 | `{"detail": "gate_unmet", "facts": {"gate": "G1", "engagement_id": "…"}}` | create or a recorded letter before G1 |
| 409 | `{"detail": "letter_before_acceptance", "facts": {"engagement_id": "…"}}` | a signature date before the acceptance decision |
| 409 | `{"detail": "possible_duplicate", "facts": {"engagement_id": "…"}}` | create without `confirm_duplicate` when the same type and period exists |
| 409 | `{"detail": "stale_version", "facts": {"draft_id": "…"}}` | autosave with an old `seen_version` |
| 409 | `{"detail": "engagement_archived"}` | any write on an archived engagement (`archived_write: deny`) |
| 409 | `{"detail": "letter_exceptions_off", "facts": {"engagement_id": "…"}}` | "Not required this year" while `allow_letter_exceptions` is unregistered (DEC-224) |
| 422 | `{"detail": "unknown_engagement_type"}` | a draft or create naming a code outside the catalogue, `single_audit` included |

## 7. Audit and outbox events
| Event | Written when | Payload (no Restricted data) |
|---|---|---|
| `engagement.created` (audit, outbox; exists) | create from a draft | engagement id, type, actor |
| `engagement_draft.started_acceptance` (audit) | start acceptance | draft id, engagement id, acceptance record id, actor |
| `letter.recorded` (audit) | a recorded letter | engagement id, mode, actor |
| `gate.met` (outbox) | G1, G2 or the interim G3 becomes met | engagement id, gate |
| `independence.requested` (exists) | create staffs a member | engagement id, user id |

Draft autosaves are operational state, not audited.

## 8. Example payloads
Brightwater Hale, synthetic; ids are placeholders.

`GET /v1/engagements/index?letter=not_signed&tile=accepted` (ENG-01 b): four rows, all `"status": "accepted"` with `"letter": {"status": "not_signed", …}`; the Thornbury estate Prospect is not a row; `"summary": {"prospect": 1, "awaiting_letter": 4, "past_due": 2}`.

`GET /v1/engagements/{id}/gates` (ENG-02 b, Northwind 401(k) PY2025 EBP Audit): `[{"gate": "G1", "met": true, …}, {"gate": "G2", "met": true, …}, {"gate": "G3", "met": true, …}, {"gate": "G4", "met": false, "blockers": [{"type": "…", "id": "…", "reason_code": "…"}]}]`.

`GET /v1/engagement-types`: 18 entries, Tax 8 · Audit & assurance 8 · CAS & Advisory 2; `soc1` and `soc2` carry `"entitlement": "attest"` and are `needs_entitlement` without it; no `single_audit`.

`POST /v1/engagement-drafts/{id}/create` for Morgan & Kai Ferris' TY2025 Form 1040 (ENG-03 e) without `confirm_duplicate` → 409 `possible_duplicate`; with `{"confirm_duplicate": true}` → 201.

## 9. Consumer contract tests
- Stub: `backend/tests/contracts/engagements_v2/test_engagements_v2_stub.py` (SPEC-321 AC-10 to AC-15).
- Consumers (P-07-T06): `backend/tests/contracts/engagements_v2/test_engagements_v2_consumer.py` (SPEC-321 AC-23 to AC-25, reusing F-02-T11's module) and `apps/web/src/fixtures/contracts/clients-engagements.test.ts` (typed ENG-01 b, ENG-02 b gates and the 18-card catalogue). F-02-T11's C1 check (`tests/contracts/c1_work_items/`) keeps holding that C1's `EngagementType` has no excluded type.

## 10. Versioning
Additive to C1 v1 (new operations and models; no C1 field changes). Moving the index and record to the plain paths in P-07-T15 is a breaking change for the v1 list's consumers: it ships with one sprint of overlap.

| Version | Frozen on | Overlap ends | Notes |
|---|---|---|---|
| v2 | | | stub 2026-10-23 (P-07-T05) at `/index` and `/{id}/record` |

## 11. Open points
- DEC-143: the paths beside the live routes; `client.intake` for start-acceptance (OQ-2); DEC-38's `engagement.create` cells and `gates_met(G1)` on `letter.record` land with the live routes; the catalogue as an 18-code enum; `type_code` checked by the server.
- DEC-224 (P-07-T15): sort by the earliest open work-item due date; `period` current = not archived or declined; `letter=not_signed` excludes prospects; the interim letter's columns (0124); the plain-path move and the `engagements.work_items_api` retirement deferred.
- The `next_due` windows (`past_due`, `within_7_days`, `within_30_days`) and `period` (`current`, `prior`, `all`) are the stub's reading of "Next due │ Any" and "Period │ Current"; P-07-T15 confirms them against the seed.
