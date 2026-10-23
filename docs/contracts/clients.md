# Clients family · CLI-01 and CLI-02 (v1)

| Field | Value |
|---|---|
| Register row | Screen-family contracts in `docs/contracts/README.md` (P-07 owns no C-number; §8.1) |
| Version | v1 |
| Status | live (P-07-T08, T09, 2026-10-23; the TIN reveal P-07-T10, 2026-10-24) |
| Provider epic | P-07 (`organisations`) |
| Consumers | CLI-01, CLI-02 (P-07-T12, T19); fixtures P-07-T11; T-01 (CLI-05 TIN columns), T-06 (CLI-03 on `entity_relationships`), P-02 (the `client` search projection) |
| Freeze sprint | the sprint review after the stub (P-07 §8.1) |
| Flag | `clients.v2` (default off, created 2026-10-23, expires 2027-04-21 under DEC-137's override: no flag may lapse before Feb 1, 2027) |
| Spec | `docs/specs/SPEC-321-clients-engagements-v2.md` (outline) |
| ADRs | ADR-139 (P-36 conventions), ADR-140 (P-39 per-module files), ADR-024 (metadata-only firm admin), ADR-026 (walls), ADR-031 (classification), ADR-005; DEC-43, DEC-47, DEC-52, DEC-62, DEC-128, DEC-132, DEC-138, DEC-141 |

## 1. Purpose
Consumers can rely on a clients index on the P-36 envelope (`{items, next_cursor, total, total_capped, counts, facets}`), a client record with `allowed_actions` and `version`, a per-kind overview built from registered section providers, a relationship list, a PATCH for the four editable fields, and a TIN reveal that is a live person's act. Walls use 404 semantics: a walled client is absent from rows, counts, facets and totals and nothing anywhere says one is hidden (DEC-43). Taxpayer IDs are masked in every payload except the reveal response.

**Flag and stub behaviour.** With `clients.v2` off every route below answers 404. With it on, the index (P-07-T08) and the record, overview, relationships and PATCH (P-07-T09) and the TIN reveal (P-07-T10) are live.

**Where the facts come from (DEC-153).** Organisations owns the client record, entities, contacts and relationships. Each other fact is a query its owner registers (`organisations/slots.py`), and an unregistered one fails closed:
- service lines, the active-engagements menu and the derived Manager and Preparer: engagements' open engagements (neither archived nor declined) and identity's engagement teams (Manager is `manager`; Preparer is `senior` or `staff`);
- `open_request_count`: requests' items waiting on the client (`requested`, `returned`), summed over the client's open engagements;
- `last_activity_at` and `last_activity_event_type`: the newest audit event (business time) on one of the client's open engagements or about the client itself;
- overview sections: organisations' own `entities`, `key_dates` and `contacts` (`client.read`) and engagements' `engagements` (`engagement.read_metadata`). The profile is `business` for business, nonprofit; `household` for household, trust and family; `plan_sponsor`; and `empty` (no sections) while the kind is unset.

**Existing route kept, not duplicated:** `GET /v1/firm/clients/search` (the ENG-03 client picker, SPEC-025) keeps its path and shape and now reads the widened `client.read` (it already drops walled clients).

## 2. Who may call it
Matrix: `docs/architecture/permission-matrix/organisations.yaml` (`client.read` moved there from `engagements.yaml`).

| Operation | Method and path | Matrix action | Roles allowed | Agent or system principal |
|---|---|---|---|---|
| Clients index (CLI-01) | `GET /v1/clients?kind=&office_id=&partner_id=&service_line=&status=&q=&sort=last_activity\|name&facets=&cursor=&limit=` | `client.read` | every firm role: firm admin, practice leader, quality partner, security admin, engagement partner, manager, senior, staff, reviewer, EQR reviewer, specialist, `client_service`; a partner through their engagement roles, and as `firm_partner` from P-07-T08 (metadata; walls in `visible(scope=client)`) | **denied** |
| Client record (CLI-02 subbar, rail) | `GET /v1/clients/{client_id}` | `client.read` | as the index | **denied** |
| Overview (CLI-02 canvas) | `GET /v1/clients/{client_id}/overview` | `client.read` + each section's own read action | as the index; metadata-only roles get metadata sections (ADR-024) | **denied** |
| Edit the record | `PATCH /v1/clients/{client_id}` | `client.update` | firm admin, partner (`firm_partner`); manager when live (DEC-141) | **denied** |
| Relationships | `GET /v1/clients/{client_id}/relationships?cursor=` | `client.read` | as the index | **denied** |
| Reveal a TIN | `POST /v1/client-entities/{entity_id}/tin/reveal` | `tin.reveal` | engagement partner, manager, EQR reviewer on one of the entity's client's open engagements; `mfa_recent`, a reason, `not_offshore`; senior and staff preparers deferred (DEC-141, DEC-223) | **denied** |

Client roles (`client_admin`, `client_contributor`) hold none of these actions.

## 3. Models
Code: `backend/src/abacus/modules/organisations/contract.py`. Tags: **R** restricted, **C** confidential, **I** internal.

- **`ClientRowOut`** (CLI-01 row): `id` I, `name` C, `descriptor` C, `kind` I (`household`, `business`, `plan_sponsor`, `nonprofit`, `trust_family`), `status` I (`ClientStatus`), `entity_count` I, `service_lines` I (`audit`, `tax`, `cas`, `advisory`), `is_attest_client` I (derived, DEC-128; the "Attest" tag), `office_id` I, `office_name` I, `relationship_partner_id` I, `relationship_partner_initials` I, `portal_status` I (`InvitationStatus`, the rollup), `open_request_count` I (null renders "—"), `binder_draft_only` I ("Binder draft"), `last_activity_at` I, `last_activity_event_type` I (an audit event type the UI words), `allowed_actions` I. **No Restricted field, no TIN.**
- **`ListPage[ClientRowOut]`**: `counts` per client status code over the filters minus `status`; `facets` (`kind`, `office`, `partner`, `service_line`) only when `facets=true`; `total` exact (DEC-47). There is no `hidden_by_wall` field.
- **`ClientRecordOut`**: `id` I, `name` C, `descriptor` C, `kind` I, `status` I, `is_attest_client` I, `risk_tier` I, `primary_office_id` I, `office_name` I, `relationship_partner_id` I (Team band Partner), `manager_user_ids` I and `preparer_user_ids` I (derived from engagement teams, DEC-62, DEC-138), `portal_status` I, `entities` R (`ClientEntityBriefOut`), `active_engagements` C (`ClientEngagementBriefOut`: `id`, `name`, `status` `EngagementStatus`, `service_line`), `tab_counts` I (`ClientTabCountsOut`: `engagements`, `relationships`, `contacts`, `messages`), `version` I, `allowed_actions` I.
- **`ClientEntityBriefOut`**: `id` I, `name` C, `entity_type` I, `fye_month_day` I, `state_of_formation` I, `plan_number` I, `tin` R (`MaskedTinOut` or null).
- **`MaskedTinOut`**: `kind` I (`ssn`, `ein`, `itin`), `presence` I (`on_file`, `applied_for`), `last4` R (`^[0-9]{4}$`, null when applied for). The UI formats `XX-XXX0287` / `•••-••-2208`.
- **`ClientOverviewOut`**: `client_id` I, `profile` I (`business`, `household`, `plan_sponsor`, `empty`), `sections` C (`ClientOverviewSectionOut`: `code` I, `kind` I `stats`/`details`/`table`/`key_dates`/`activity`, `read_action` I, `items` C, `total` I). **`ClientOverviewItemOut`**: `key` I, `text` C, `figure` C (decimal string, computed in code, ADR-050), `on` I, `at` I, `pill_object` I and `pill_code` I (a C2 status the UI words), `ref` I (`ClientObjectRefOut`: `type`, `id`).
- **`ClientRelationshipOut`**: `id` I, `kind` I (`spouse`, `owner_of`, `trustee_of`, `beneficiary_of`, `sponsor_of`, `upper_tier_of`, `executor_of`, `gp_of`, `lp_of`, `estate_of`), `from_entity_id` I, `from_entity_name` C, `to_entity_id` I, `to_entity_name` C, `to_client_id` I, `percent` C (decimal string), `effective_from` I, `effective_to` I.
- **`ClientPatchIn`**: `seen_version` I (required), `descriptor` C (1–120, one line), `primary_office_id` I, `relationship_partner_id` I, `status_change` I (`ClientStatusChangeIn`: `status` `ClientStatus`). Absent fields are unchanged.
- **`TinRevealIn`**: `reason` I, a registry code: `prepare_return`, `review_return`, `file_or_correct_filing`, `respond_to_notice`, `verify_identity` (DEC-141).
- **`TinRevealOut`**: `entity_id` I, `kind` I, `value` R (the plain TIN, once), `remask_after_seconds` I (10). Served with `Cache-Control: no-store`. The only schema that carries a plain TIN.

## 4. Status words
`client` (P-07-T03): `prospect` Prospect · `active` Active · `inactive` Inactive · `former` Former. Portal rollup `invitation`: `not_invited` Not invited · `invited` Invited · `active` Active (the column carries no `locked` or `deactivated`). `engagement` for the active-engagements menu. Overview pills name their own object's codes.

## 5. Human-only actions
`tin.reveal` and `client.update` deny `agent` and `system` at the matrix; the reveal route also requires a live human through `authorise` (agent and system principals have no role on a firm resource) and recent MFA. The reveal also writes an insert-only `tin_reveals` row (`actor_kind = 'human'` CHECK, migration 0123) that the audit event points at: who, which entity, the engagement whose role allowed it, the reason code and the MFA time, never the value (DEC-223).

## 6. Errors
| Status | Body | When |
|---|---|---|
| 404 | `{"detail": "not found"}` | `clients.v2` off; a walled or unknown client or entity |
| 403 | `{"detail": "forbidden"}` | no action; an offshore member, stale MFA or no role on the client's open engagements on reveal |
| 404 | `{"detail": "not found"}` | reveal: no TIN on file for the entity |
| 409 | `{"detail": "tin_conflict", "facts": {"client_entity_id": "…"}}` | `seal_tin` (no route yet): the TIN is on file for another entity of the firm |
| 422 | `{"detail": "tin_kind_not_allowed", "facts": {"client_entity_id": "…"}}` | `seal_tin`: an SSN or ITIN on a firm that is not synthetic, until C19 |
| 409 | `{"detail": "stale_version", "facts": {"client_id": "…"}}` | PATCH with an old `seen_version` |
| 409 | `{"detail": "illegal_transition", "facts": {"client_id": "…"}}` | a person moves a prospect to active |
| 422 | `{"detail": "cursor_invalid"}` | a cursor from another list, filter set or firm |
| 422 | validation | an unknown reason code, a descriptor over 120 characters |

## 7. Audit and outbox events
| Event | Written when | Payload (no Restricted data) |
|---|---|---|
| `client.updated` (audit, outbox) | PATCH changes a field | client id, changed field names, actor |
| `tin.revealed` (audit only) | a reveal succeeds | target the entity, `after` the `tin_reveals` id (reason code there), scope the engagement, actor; never the value |

Reads are not audited, except reveals.

## 8. Example payloads
Brightwater Hale, synthetic. Ids are placeholders.

`GET /v1/clients?status=active` (CLI-01 a, first row of 16):
```json
{"items": [{"id": "…", "name": "Ridgeline Property Partners, LP", "descriptor": null, "kind": "business",
  "status": "active", "entity_count": 1, "service_lines": ["tax", "advisory"], "is_attest_client": false,
  "office_id": "…", "office_name": "New York", "relationship_partner_id": "…", "relationship_partner_initials": "DR",
  "portal_status": "active", "open_request_count": 5, "binder_draft_only": false,
  "last_activity_at": "…", "last_activity_event_type": "…", "allowed_actions": []}],
 "next_cursor": "…", "total": 184, "total_capped": false, "counts": {"active": 184}, "facets": {}}
```
For Lena Park (CLI-01 c) the same request has the same keys, Ashford is not a row and `total` is 183.

`GET /v1/clients/{id}` (CLI-02 a, Ridgeline): `entities[0].tin` is `{"kind": "ein", "presence": "on_file", "last4": "0287"}`, rendered `XX-XXX0287`; `tab_counts` `{"engagements": 2, "relationships": …, "contacts": 5, "messages": 1}` (CLI-02 a tabs).

`POST /v1/client-entities/{id}/tin/reveal` `{"reason": "prepare_return"}` → `{"entity_id": "…", "kind": "ein", "value": "00-0000287", "remask_after_seconds": 10}` (the seed holds no real TIN; blueprint §9).

## 9. Consumer contract tests
- Stub: `backend/tests/contracts/clients/test_clients_stub.py` (SPEC-321 AC-1 to AC-5).
- Consumers (P-07-T06): `backend/tests/contracts/clients/test_clients_consumer.py` (SPEC-321 AC-20 to AC-22: envelope, no wall field anywhere, masked TIN only, registry codes) and `apps/web/src/fixtures/contracts/clients-engagements.test.ts` (typed CLI-01 a/c and CLI-02 a frames).

## 10. Versioning
Additive changes in place. Breaking changes ship as v2 with one sprint of overlap (see `docs/contracts/README.md`).

| Version | Frozen on | Overlap ends | Notes |
|---|---|---|---|
| v1 | | | stub 2026-10-23 (P-07-T04); index, record, overview, relationships and PATCH live 2026-10-23 (P-07-T08, T09) |

## 11. Open points
- DEC-223 (P-07-T10): the reveal is authorised per open engagement of the client; the response is `Cache-Control: no-store`; 422 `tin_kind_not_allowed` and 409 `tin_conflict` come from `organisations.api.seal_tin` (intake, P-07-T42, is its first route); a counter counts reveals by reason; ADR-167's `pii_kind` flag waits for its acceptance.
- DEC-141: `not_offshore` on the reveal and `firm_partner` on reads land with the live routes (a condition without its registered facts fails closed); the PATCH status change is nested (`status_change`) so that every status field in the document is a plain enum; the reveal reason codes; the manager and preparer paths added when live; the reveal response as the one plain-TIN payload.
- The facet keys and the `last_activity_event_type` wording table are confirmed by P-07-T08 and P-07-T11.
