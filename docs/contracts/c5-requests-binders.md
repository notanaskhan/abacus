# C5 · Requests and binders, the binders and requests half (v1)

| Field | Value |
|---|---|
| Register row | C5 in `docs/contracts/README.md` |
| Version | v1 |
| Status | stub (BND-01, BND-02, SHL-14 family incl. portal mark-done, ignore, upload intents and withdraw: P-06-T01, 2026-10-22). The SHL-20 family (screening, follow-ups) is added in place as v1.2 (§12): the follow-ups v2 routes are live (P-06-T14, 2026-10-24) and the screening routes are a stub behind `screening.card` (P-06-T15, 2026-10-24). The portal-scopes half is P-08's: `portal-identity.md` (v1.1, P-08-T01, 2026-10-23) |
| Provider epic | P-06 (binders and requests half); P-08 (portal scopes). Schema half: F-03-T14, F-03-T15, F-03-T26 |
| Consumers | A-01 (AUD-03), R-01 (POR-03, POR-04, POR-14, POR-20), T-02, C-01 (CLS-03), K-01, N-01, A-03, N-03, K-04, I-01. Screens: BND-01, BND-02, SHL-14 |
| Freeze sprint | S3 (starts 2026-11-30); freeze Fri 2026-12-11 |
| Flag | `binders.engine` (default off, created 2026-10-22, expires 2027-01-20). The withdraw route moves to `evidence.withdrawal` when P-06-T19 creates it (ADR-162 §3) |
| Spec | `docs/specs/SPEC-319-requests-binders-engine.md` (outline) |
| ADRs | ADR-139 (P-36 conventions), ADR-140 (P-39 per-module files), ADR-161 (P-35 Undo), ADR-162 (P-31 withdrawal), ADR-005, ADR-031; DEC-09, DEC-20, DEC-31, DEC-37, DEC-38, DEC-58, DEC-74, DEC-136 |

## 1. Purpose
Consumers can rely on binders as many `request_lists` per work item with a five-state lifecycle, on requests with the DEC-09 status set and the client's words, on the client's portal actions (mark done, ignore with a reason, upload intents, withdraw an unaccepted upload), and on a fixed set of human-only operations whose matrix rows deny the agent. Lists use the P-36 envelope; records carry `allowed_actions`; errors are catalogue codes with identifier-only facts; client-visible effects take an `Idempotency-Key`.

**Stub behaviour.** With `binders.engine` off every route below answers 404. With it on, each answers 501 `not_implemented` until its task lands: P-06-T19 (withdraw) and the follow-up override. **Implemented (P-06-T10, 2026-10-23):** the request lifecycle (PATCH, delete, send and its Undo, waive, return to client, delegate, incorporate, activity), the client's Ignore, upload intents and the live poll (DEC-158). **Implemented (P-06-T11):** the index read model. **Implemented (P-06-T07, 2026-10-23):** create, the binder record, its rows, publish and its Undo, unpublish, duplicate, recipients, the client preview, binder activity and the portal mark-done. These no longer document 501, an expected contract transition (`test_c5_stub.py` `IMPLEMENTED`). The Brightwater Hale binder slice and `stub_from_seed` arrive with P-06-T08 and F-04, so the stubs return no fixtures yet; the screens build on fixture scenarios typed with the generated client.

**Existing routes kept, not duplicated:** `POST/GET /v1/engagements/{eid}/request-items` (P-06-T10 extends the body additively: `title`, `category_id`, `period_start/end`, `due_on`, `wave`, `kind`, `firm_owner_user_id`, `linked_ref`, `supports_ref`; `binder_id` required while `binders.engine` is on), `PUT …/{id}/client-visibility`, `PUT …/{id}/client-assignee`, `GET …/request-items/{id}/client-view` (extended for drafts in T10), SPEC-042's `client-response` and `client-done` (until R-01 moves to the portal routes), and `POST …/evidence-versions/{vid}/decision/accept · reject · send-back`.

## 2. Who may call it
Matrix: `docs/architecture/permission-matrix/requests.yaml`, `evidence.yaml`. "Firm setting" means the cell is `firm_setting(<key>)` and allows only while the firm turns the key on.

| Operation | Method and path | Matrix action | Roles allowed | Agent or system principal |
|---|---|---|---|---|
| Binders index (BND-01) | `GET /v1/binders?service=&season=&office=&preparer=&client_activity=any\|none_30_days&status=&q=&cursor=&limit=` | `binder.read` | partner, manager, senior, staff, reviewer, `client_service` (metadata, DEC-20); practice leader and quality partner in scope; client admin client-visible only; contributor assigned only | agent `task_scope`; system denied |
| Create a binder | `POST /v1/binders` | `binder.create` | partner, manager; senior (`seniors_can_publish`) and `client_service` (`client_service_can_publish`) by firm setting | **denied** |
| Binder record (BND-02) | `GET /v1/binders/{binder_id}` | `binder.read` | as the index | agent `task_scope` |
| Binder rows | `GET /v1/binders/{binder_id}/requests?category=&cursor=` | `request_item.read` | as the existing row | agent `task_scope` |
| Live poll (5 s) | `GET /v1/binders/{binder_id}/live` | `request_item.read` | as above | agent `task_scope` |
| Publish | `POST /v1/binders/{binder_id}/publish` + `Idempotency-Key` | `binder.publish` | partner, manager; senior and `client_service` by firm setting | **denied** |
| Undo publish (10 s) | `POST /v1/binders/{binder_id}/publish/undo` | `binder.publish` | as publish | **denied** |
| Unpublish | `POST /v1/binders/{binder_id}/unpublish` `{reason}` | `binder.publish` | as publish | **denied** |
| Duplicate as pt n+1 | `POST /v1/binders/{binder_id}/duplicate` | `binder.create` | as create | **denied** |
| Recipients | `PUT /v1/binders/{binder_id}/recipients` `{contact_ids}` | `binder.update` | as create | **denied** |
| Follow-up override | `PUT /v1/binders/{binder_id}/follow-up-override` `{override}` | `binder.update` | as create | **denied** |
| Preview as client | `GET /v1/binders/{binder_id}/client-preview` | `binder.read` | as the index | agent `task_scope` |
| Binder activity | `GET /v1/binders/{binder_id}/activity?cursor=` | `activity.read` (existing) | firm admin, practice leader, partner, manager, senior, staff, reviewer | denied |
| Edit a request | `PATCH /v1/engagements/{eid}/request-items/{id}` | `request_item.update` (existing) | partner, manager, senior, `client_service` | denied |
| Delete a never-sent draft | `DELETE /v1/engagements/{eid}/request-items/{id}` | `request_item.update` | as above | denied |
| Send | `POST …/request-items/{id}/send` + `Idempotency-Key` | `request_item.send` | partner, manager, senior, staff, `client_service`; independence required | **denied** |
| Undo send (10 s) | `POST …/request-items/{id}/send/undo` | `request_item.send` | as send | **denied** |
| Waive | `POST …/request-items/{id}/waive` `{na_reason, note}` | `request_item.waive` (existing; reason required) | partner, manager | denied |
| Return to client | `POST …/request-items/{id}/return-to-client` `{note?}` + `Idempotency-Key` | `request_item.return` | partner, manager, senior, staff | **denied** |
| Delegate to a third party | `POST …/request-items/{id}/delegate` `{contact_id}` | `request_item.delegate` | partner, manager, senior | **denied** |
| Mark incorporated (close) | `POST …/request-items/{id}/incorporate` | `request_item.update` | partner, manager, senior, `client_service` | denied |
| Request activity | `GET …/request-items/{id}/activity?cursor=` | `activity.read` | as binder activity | denied |
| Mark binder done (client) | `POST /v1/portal/binders/{binder_id}/mark-done` | `binder.mark_done` | client admin (client-visible only), contributor (assigned only); no firm role | **denied** |
| Ignore a request (client) | `POST /v1/portal/request-items/{id}/ignore` `{reason, note?}` | `request_item.ignore` (reason required) | client admin, contributor; no firm role | **denied** |
| Upload intent (client) | `POST /v1/portal/request-items/{id}/upload-intents` `{files_expected}` | `evidence.upload` (existing) | partner, manager, senior, staff, client admin, contributor (assigned) | agent denied; system allowed (retrievals) |
| Withdraw an unaccepted upload (client) | `POST /v1/engagements/{eid}/evidence-versions/{vid}/withdraw` + `Idempotency-Key` | `evidence.withdraw` | client admin (client-visible only; may withdraw a contributor's upload in scope), contributor (own uploads only); every firm role denied | **denied** (agent and system) |
| Accept / reject an upload (existing routes) | `POST …/evidence-versions/{vid}/decision/accept · reject · send-back` | `evidence.accept` · `evidence.reject` | partner, manager; senior (`seniors_can_accept`) and now **staff** (`staff_can_accept_evidence`, DEC-37) by firm setting; independence required | **denied** |

Portal routes run under the firm context until P-08's portal principal and BFF land; they then take the portal principal with `scope_only`. Per-kind refinements that the matrix grammar cannot express (conditions apply to the whole action and only narrow, DEC-132) are applied in the service when the routes go live: `not_offshore` on `tax_return` binders (fails closed until C19) and the OQ-1 preparer path on `tax_return` binders (DEC-136, P-06-T07).

## 3. Models
Code: `backend/src/abacus/modules/requests/contract.py`, `backend/src/abacus/modules/evidence/contract.py`. Every field is tagged (ADR-031). Confidential: names, titles, client wording, reasons and notes, `supports_ref`. Everything else is internal (identifiers, codes, dates, counts). No Restricted field and no TIN appears in any C5 payload.

- **`BinderRowOut`** (BND-01 row, in `ListPage[BinderRowOut]`): `id`, `engagement_id`, `work_item_id`, `client_name`*, `work_item_label`*, `name`*, `kind` (`organizer · pbc · close_intake · intake · third_party`), `part`, `status` (`BinderStatus`), `preparer_user_id`, `done_count`, `total_count`, `last_client_activity_at`, `unpublished_at`, `unpublished_by`, `unpublish_reason`*, `tags` (registered codes), `allowed_actions`. The envelope's `counts` are per binder status (the tiles), computed after `visible()`; `total` is the visible total ("Showing 15 of 241"). Added in place by P-06-T11 (all optional, all internal but one): `service` (the Service chip's code: `tax_returns`, `assurance`, `closes`, `notices`, `advisory_projects`), `season` (`TY<year>` for a return, the year its period begins; `FY<year>` for other work), `office_id`, `published_at`; the Complete line's `marked_done_at`, `marked_done_by` and `marked_done_by_name`*; the Closed line's `closed_at` and `closed_reason` (a registered close-rule code); the Count's `overdue_count`; and "n requested Sep 8-10" as `requested_count`, `requested_from` and `requested_to` (business dates). Each facet leaves out its own filter; `facets` are `service`, `season`, `office`, `preparer`, `client_activity` (`any`, `none_30_days`) and `part` (`1` returns, `2+` second-part binders). `client_activity=none_30_days` keeps Published binders whose last client activity (else their publish) is more than 30 business days old. Rows sort by status in the tiles' order, then newest client activity. The last-activity summary and its Inbox link wait for the projection columns (§11).
- **`BinderOut`** (BND-02 record): identity and kind fields as the row, `created_from` (`blank · template · prior_year_binder · engine_import`), `prior_year_source_ref`, `template_ref`, `default_due_on`, `recipients [{contact_id, name*}]`, `categories [{id, name*, position, done_count, total_count}]`, `done_count`, `total_count`, `published_at/by`, `unpublished_at/by/reason*`, `marked_done_at/by`, `marked_done_open_count`, `closed_at`, `closed_reason` (a registered close-rule code), `follow_up_override {every_days 1..30, max 1..4}`, `undo_until`, `allowed_actions`.
- **`BinderIn`**: `work_item_id`, `kind`, `name?`*, `from_binder_id?`, `template_ref?`. **`UnpublishIn`**: `reason`* (1..300). **`RecipientsIn`**: `contact_ids` (≤ 50). **`FollowUpOverrideIn`**: `override` (null clears).
- **`BinderRequestRowOut`** (in `ListPage[BinderRequestRowOut]`, `counts` per request status): `id`, `category_id`, `title`*, `status` (`RequestStatus`), `overdue` (derived), `client_visible`, `kind` (`client_upload · firm_provided`), `due_on`, `requested_at`, `client_ignored_at`, `client_ignore_reason`, `source_tag` (`prior_year`), `incorporation_state`, `screening` (`EvidenceScreeningStatus`, the glyph only), `linked_count`, `upload_count`, `allowed_actions`.
- **`BinderLiveOut`**: `items [{request_item_id, uploading_files, inbox_waiting, screening_running}]`, `as_of`.
- **`BinderClientPreviewOut`**: `binder_id`, `name`*, `status`, `items [{id, category_name*, title*, description*, status, client_ignored, due_on}]`: the portal projection, never internal fields, sample parameters or materiality.
- **`ActivityEventOut`** (in `ListPage`): `id`, `event_type`, `at`, `actor_kind` (`human · agent · system`), `actor_user_id`, `via_agent`, `target_type`, `target_id`. Identifiers only; the UI words them. A withdrawn upload's event never carries the file name.
- **`RequestItemV2Out`** (SHL-14 record): `id`, `engagement_id`, `binder_id`, `category_id`, `title`*, `description`* (client wording), `status`, `overdue`, `client_visible`, `kind`, `wave` (`planning · year_end · sample`), `period_start/end`, `due_on`, `client_assignee_user_id`, `firm_owner_user_id`, `supports_ref`*, `linked_ref {kind: workpaper · procedure_step · k1_package, id}`, `source_tag`, `requested_at`, `sent_at`, `sent_by`, `drafted_by_run_id`, `drafted_wording_source` (`template · model`), `na_reason`, `na_by`, `na_at`, `client_ignored_at`, `incorporation_state`, `incorporated_by/at`, `undo_until`, `allowed_actions`.
- **`RequestItemPatchIn`**: every editable field optional. **`WaiveIn`**: `na_reason` (`not_applicable_this_year · already_sent · dont_have · firm_waived`), `note`* (1..1000). **`ReturnToClientIn`**: `note?`*. **`DelegateIn`**: `contact_id` → **`DelegationOut`** `{request_item_id, contact_id, grant_id, granted_by, granted_at}`. **`RequestItemDeletedOut`** `{request_item_id, deleted_at}`.
- **`IgnoreIn`**: `reason` (SPEC-042's codes `not_this_year · sent_another_way · dont_have`), `note?`* (≤ 500) → **`IgnoredOut`** `{request_item_id, status, client_ignored_at}`.
- **`UploadIntentIn`**: `files_expected` 1..50 → **`UploadIntentOut`** `{request_item_id, files_expected, expires_at}` (90 s).
- **`BinderMarkedDoneOut`**: `{binder_id, status, marked_done_at, open_count}`. **`WithdrawalOut`**: `{evidence_version_id, request_item_id, withdrawn_at, erase_after}`.

(* confidential)

## 4. Status words
From `docs/product/status-vocabulary.yaml` (C2), generated enums only:
- `binder`: `draft` Draft · `published` Published · `unpublished` Unpublished · `complete` Complete ("Marked done by {person}") · `closed` Closed.
- `request` (DEC-09): `draft` Draft · `requested` "Requested {date}" · `uploaded` "Uploaded – needs review" · `received` "Received ✓" · `returned` "Returned · {reason}" · `not_applicable` "Not applicable" · derived `overdue` (never stored).
- Client words are each code's `client_label`: To do · Done · Returned · Ignored. A client Ignore keeps `requested` with `client_ignored_at` set and reads "Ignored" (OQ-3).
- `request_close`: `pending_incorporation`, `incorporated` (SHL-14 d) through `incorporation_state`.
- `evidence_screening` glyph: `passed` · `flagged` · `not_screened`.

## 5. Human-only actions
Denied to the agent at the matrix (`agent: deny`, proven by `tests/security/test_agent_principal.py` and `tests/contracts/c5_requests_binders/test_c5_stub.py`); at go-live the services also refuse an agent context (`banned_patterns` AGENT rules) and record the human actor (INV-1, INV-5):

| Action | Operation | Who |
|---|---|---|
| `binder.create`, `binder.update` | create, duplicate, recipients, follow-up override | a firm person |
| `binder.publish` | publish, Undo, unpublish | a firm person |
| `request_item.send` | send, Undo | a firm person (an agent's draft is sent by the person who approves it, SHL-14 f) |
| `request_item.return` | return a client Ignore to the client | a firm person |
| `request_item.delegate` | delegate to a third party | a firm person |
| `request_item.waive` (existing) | waive to Not applicable | partner or manager, with a reason |
| `evidence.accept`, `evidence.reject` (existing) | accept or return an upload | a firm person (staff by DEC-37 setting) |
| `binder.mark_done`, `request_item.ignore`, `evidence.withdraw` | the client's own acts | a client person only; every firm role and the agent denied |

Client-facing sends (publish, send, return to client) are held by a P-04-T10 approval grant with `not_before = +10 s` and dispatched by P-06-T06's delivery, which consumes the grant (DEC-24, ADR-161).

## 6. Errors
Codes are reserved for the implementing tasks; they enter `docs/architecture/error-codes.yaml` when the classes that raise them land. Facts are identifiers only.

| Status | Body | When |
|---|---|---|
| 404 | `{"detail": "not found"}` | `binders.engine` off; a walled, out-of-scope or other-firm binder or request (INV-3, INV-4) |
| 501 | `{"detail": "not_implemented"}` | stub, flag on |
| 409 | `{"detail": "binder_gate_unmet", "facts": {"gate": "G3"}}` | publish before G3, except `intake` |
| 409 | `{"detail": "binder_not_draft"}` | publish or edit from a state that doesn't allow it |
| 409 | `{"detail": "binder_not_published"}` | unpublish or the client's mark-done on a binder that isn't Published (P-06-T07, additive) |
| 422 | `{"detail": "due_date_required", "facts": {...item ids}}` | publish or send with requests lacking a due date |
| 422 | `{"detail": "reason_required"}` | unpublish or ignore without a reason (an absent or blank `reason` field is refused first by body validation, also 422) |
| 409 | `{"detail": "request_already_sent"}` | delete a sent request |
| 409 | `{"detail": "out_of_scope"}` | client wording fails `communications` scope check |
| 409 | `{"detail": "model_text_not_permitted"}` | unchanged model-drafted wording while P-25 is off (DV-11) |
| 409 | `{"detail": "undo_window_closed"}` / `{"detail": "effect_started"}` | Undo after 10 s / after delivery began |
| 409 | `{"detail": "evidence_accepted"}` | withdraw an ever-accepted version |
| 403 | `{"detail": "not_your_upload"}` | a contributor withdraws someone else's upload |
| 422 | `{"detail": "idempotency_key_reused"}` | the same key with a different body (P-06-T06) |

## 7. Audit and outbox events
Audit events (UoW `tx.record`, identifiers and fingerprints only; P-06 §4.7):

| Event | Written when | Payload (no Restricted data) |
|---|---|---|
| `binder.created`, `binder.duplicated` | create, duplicate | binder id, work item id, `created_from`, part |
| `binder.published`, `binder.publish_undone` | publish, Undo | binder id, item ids sent, grant id |
| `binder.unpublished` | unpublish | binder id, reason fingerprint |
| `binder.recipients_changed` | recipients | binder id, contact ids |
| `binder.marked_done` | client mark-done | binder id, contact id, open count |
| `binder.closed` | work item terminal (actor `system`) | binder id, rule code |
| `request_item.drafted`, `request_item.created`, `request_item.updated` | create (agent draft carries `drafted_by_run_id`), edit | item id, changed field names |
| `request_item.sent`, `request_item.send_undone` | send, Undo | item id, grant id, `sent_by` |
| `request_item.visibility_changed` | visibility (existing route) | item id, visible |
| `request_item.waived` | waive | item id, `na_reason` |
| `request_item.ignored_by_client` | client Ignore | item id, reason code |
| `request_item.returned_to_client` | return to client | item id |
| `request_item.deleted` | delete draft | item id |
| `request_item.delegated` | delegate | item id, contact id, grant id |
| `request_item.incorporated` | incorporate | item id |
| `review_decision.*` (existing) | accept / reject / send back | version id, decision |
| `evidence_version.withdrawn` | withdraw | version id, request item id (no file name) |
| `evidence_withdrawal.erased`, `evidence_withdrawal.erase_blocked` | purge (P-06-T19) | version id, hold reference |
| `idempotency.replayed` | kernel replay (metrics only) | route, key fingerprint |

Outbox events (P-06 §4.6): `binder.published`, `binder.unpublished`, `binder.marked_done`, `binder.closed`, `request_item.sent`, `request_item.status_changed`, `request_item.ignored`, `request_item.returned_to_client`, `evidence_version.withdrawn`, `evidence_withdrawal.erased`. Client-facing deliveries carry `not_before` and the approval grant id. Notification kinds (C16, undotted): `binder_published`, `request_item_sent`, `request_item_returned_to_client`, `binder_marked_done`, `request_item_ignored`.

## 8. Example payloads
Brightwater Hale, synthetic. Real fixtures come from the binder slice (P-06-T08); these are shapes only.

`GET /v1/binders?service=tax_returns&season=TY2025` (BND-01 a, Grace Holloway):
```json
{"items": [{"id": "…", "engagement_id": "…", "work_item_id": "…", "client_name": "Claire Feld",
  "work_item_label": "2025 Form 1040", "name": "Feld 2025 Binder", "kind": "pbc", "part": 1,
  "status": "published", "preparer_user_id": "…", "done_count": 5, "total_count": 7,
  "last_client_activity_at": "2026-09-14T14:02:00Z", "tags": [], "allowed_actions": ["binder.read"],
  "service": "tax_returns", "season": "TY2025", "overdue_count": 0, "requested_count": 2,
  "requested_from": "2026-09-08", "requested_to": "2026-09-10"}],
 "next_cursor": "…", "total": 241, "total_capped": false,
 "counts": {"draft": 1, "published": 48, "unpublished": 0, "complete": 40, "closed": 152},
 "facets": {"part": [{"value": "1", "label": "Returns", "n": 224},
                     {"value": "2+", "label": "Second-part binders", "n": 17}]}}
```

`POST /v1/binders/{id}/unpublish` without a reason: `422 {"detail": "reason_required"}`. Before G3: `409 {"detail": "binder_gate_unmet", "facts": {"gate": "G3"}}`.

`POST /v1/portal/request-items/{id}/ignore` (Paul Thornbury): `{"reason": "not_this_year"}` → `{"request_item_id": "…", "status": "requested", "client_ignored_at": "2026-09-10T15:20:00Z"}`.

`POST …/evidence-versions/{vid}/withdraw` on an accepted version: `409 {"detail": "evidence_accepted"}`.

## 9. Consumer contract tests
- Provider stub test: `backend/tests/contracts/c5_requests_binders/test_c5_stub.py` (every route and action, Idempotency-Key, C2 enums, agent denies, flag off 404 / on 501; SPEC-319 AC-1 to AC-4).
- Consumer tests for A-01, R-01, T-02, C-01 (shapes, draft invisibility to client principals, client words, the 9.5.6 codes): P-06-T02 in `backend/tests/contracts/c5_requests_binders/` plus TypeScript fixture assertions. They run in the provider's CI.

## 10. Versioning
Additive changes in place. Breaking changes ship as v2 with one sprint of overlap (see `docs/contracts/README.md`).

| Version | Frozen on | Overlap ends | Notes |
|---|---|---|---|
| v1 | (planned 2026-12-11) | | stub 2026-10-22 (P-06-T01); SHL-20 family additive in P-06-T15 |
| v1.1 | (planned 2026-12-11) | | additive, 2026-10-23 (P-08-T01): the portal half (portal identity and home, POR-01 and POR-02) in `docs/contracts/portal-identity.md`; nothing in this half changes |
| v1.1 | (planned 2026-12-11) | | additive, 2026-10-23 (P-06-T11): `GET /v1/binders` live; `BinderRowOut` gains the status-line facts and `service`, `season`, `office_id`, `published_at`; facets named |
| v1.2 | (planned 2026-12-11) | | additive, 2026-10-24 (P-06-T14, P-06-T15): the SHL-20 family (§12): follow-ups v2 live behind `binders.engine`; the screening card, rerun, feedback and screening-return draft as a stub behind `screening.card` |

## 11. Open points
- DEC-136: OQ-1 mechanism (preparer publish on tax-return binders), firm-setting key names, portal ignore vs SPEC-042, staff create deferred to P-06-T10.
- ADR-162 (P-31, the plan's "ADR-137") is accepted; the withdraw route follows it.
- BND-01's last-activity summary ("Claire emailed 2 files (Inbox) · uploading 2 now") and its INB-04 link need `binder_activity` to carry the activity's kind, actor, file count and inbox thread (a migration); until then the row has `last_client_activity_at` only. The projection is kept today by the client's mark-done; portal upload, answer, sign and `inbox_file.added` subscribers follow with that migration.
- P-08 owns the portal principal; until it lands the `/v1/portal` routes take the firm context. The portal half is `docs/contracts/portal-identity.md` (C5 v1.1, P-08-T01).

## 12. The SHL-20 family: follow-ups and evidence screening (v1.2, additive)
Spec: SPEC-319 Story 5 (AC-16 to AC-20); P-06 §3.2 Story 2.2, §3.5–3.6, §4.3; DEC-74, DEC-79, DEC-220.

**Behaviour.** The follow-ups v2 routes are **live** behind `binders.engine` (off: 404), with the screens that use them (BND-01 b, BND-02 d, SHL-20 b). The screening routes and the screening-return draft are a **stub** behind `screening.card` (default off, created 2026-10-24, expires 2027-01-22): off, 404 and the card area shows nothing extra; on, 501 `not_implemented` until P-06-T20 (card, rerun, feedback) and P-06-T22 (the screening-return draft and its send: two `send_back` decisions with the reason, the request `returned` and a shared comment carrying the sender's final text, in one unit of work). The SPEC-027 engagement routes (`/v1/engagements/{eid}/follow-ups…`) stay and compose from the same template.

| Operation | Method and path | Matrix action | Roles allowed | Agent or system principal |
|---|---|---|---|---|
| Draft follow-ups (BND-01 b, BND-02 d) | `POST /v1/follow-ups/drafts` `{binder_ids[] \| request_item_ids[]}` | `follow_up.draft` | partner, manager, senior, staff, `client_service` | agent `task_scope` (the P-4 tick drafts) |
| A follow-up (the email as it will be sent) | `GET /v1/follow-ups/{follow_up_id}` | `follow_up.draft` | as draft | agent `task_scope` |
| Edit before sending | `PATCH /v1/follow-ups/{follow_up_id}` `{body}` | `follow_up.draft` | as draft | **denied** at the service (a person's edit) |
| Send | `POST /v1/follow-ups/{follow_up_id}/send` + `Idempotency-Key` | `follow_up.send` | partner, manager, senior, staff, `client_service` | **denied** |
| Send several | `POST /v1/follow-ups/send` `{ids[]}` + `Idempotency-Key` | `follow_up.send` | as send | **denied** |
| Undo send (10 s, by its sender) | `POST /v1/follow-ups/{follow_up_id}/undo` | `follow_up.send` | as send | **denied** |
| Dismiss | `POST /v1/follow-ups/{follow_up_id}/dismiss` | `follow_up.send` | as send | **denied** |
| Screening card (SHL-20 a–e) | `GET /v1/engagements/{eid}/request-items/{item_id}/screening` | `upload_review.read` (existing) | partner, manager, senior, staff, reviewer; independence required | denied |
| Re-screen current files (SHL-20 c) | `POST …/request-items/{item_id}/screening/rerun` | `screening.request` (existing) | partner, manager, senior, staff | denied |
| Feedback (SHL-20 f) | `POST /v1/screenings/{screening_result_id}/feedback` `{thumb, reason_code?, note?}` | `screening.feedback` (new) | partner, manager, senior, staff; independence required | **denied** |
| Draft a screening return (SHL-20 b) | `POST …/request-items/{item_id}/follow-ups` `{kind: screening_return, returning[], reason_code?}` | `follow_up.draft` | as draft | agent `task_scope` |

**Models** (code: `backend/src/abacus/modules/agents/follow_up_routes.py`, `screening_contract.py`; every field tagged, ADR-031; * confidential):
- **`FollowUpOut`**: `id`, `engagement_id`, `binder_id`, `kind` (`overdue · chase · screening_return`), `status` (`drafted · sent · dismissed`), `recipient_user_id`, `recipient_contact_id`, `recipient_name`*, `items [{request_item_id, title*, due_on, overdue}]` (the open requests it lists, each once; `overdue` on the firm's business date), `subject`*, `body`* (template-composed, or the person's edit; never model text, DEC-79), `edited`, `drafted_by_kind` (`agent` for every template-composed draft: the C-31 marker; `person` reserved), `template_key`, `created_at`, `sent_by`, `sent_at`, `undo_until`, `allowed_actions`. **`FollowUpDraftsIn`**: exactly one of `binder_ids` (≤ 200) and `request_item_ids` (≤ 500). **`FollowUpDraftsOut`**: `{items: [FollowUpOut]}`. **`FollowUpEditIn`**: `body`* (1..10000). **`FollowUpSendManyIn`**: `ids` (1..200).
- **`ScreeningCardOut`**: `request_item_id`, `screening_result_id` (null: not screened), `batch_no`, `verdict` (C2 `EvidenceScreeningStatus`: `passed · flagged · not_screened`), `running`, `files_total`, `files_answering`, `checks [{key: right_document · right_period, verdict: pass · flag · not_run, source: model · code, answer_ref, citation_ids}]`, `file_flags [{evidence_version_id, file_name*, reason_code: wrong_document · wrong_year, region_ref}]`, `provenance {prompt_ref, duration_ms, screened_at}`, `my_feedback`, `allowed_actions`. **No confidence field, ever.**
- **`ScreeningRerunOut`**: `{request_item_id, running, as_of}` (202). **`ScreeningFeedbackIn`**: `thumb` (`up · down`), `reason_code` (`wrong_request_match · wrong_period · unclear_file · other`; required with `down`, else 422), `note?`* (≤ 500) → **`ScreeningFeedbackOut`** `{screening_result_id, thumb, reason_code, created_at}`. **`ScreeningReturnDraftIn`**: `kind` (`screening_return`), `returning` (1..50 version ids), `reason_code` (default `wrong_document`) → `FollowUpOut`.

**Templates.** Email text is the published C16 template: `notification.follow_up_sent` (Reminder) and `notification.follow_up_sent.screening_return` (Return), imported by platform staff (`POST /v1/platform/email-templates/import`). Follow-up templates may use `recipient_first_name`, `engagement_display_name`, `firm_name`, `app_link` and the body-only block `request_list` (one request per line). Until one is imported, drafting answers 409 `follow_up_template_missing`.

**Errors** (identifier-only facts): 409 `follow_up_template_missing`; 409 `follow_up_already_sent` (edit, send or dismiss a sent one); 409 `follow_up_not_waiting` (a dismissed one); 409 `out_of_scope` (the person's added text names something outside the engagement; nothing is written); 409 `undo_window_closed` / `effect_started`; 422 `idempotency_key_reused`; 409 `screening_running` (rerun, reserved for P-06-T20); 422 body validation for a thumbs-down without a reason.

**Audit and outbox.** Audit: `follow_up.drafted`, `follow_up.edited` (edit fingerprint), `follow_up.sent` (grant id, body fingerprint; **human-only in the database**, migration 0122), `follow_up.undone`, `follow_up.dismissed`, `message.sent`/`message.blocked` (the email, created by the sender); `screening.feedback` (P-06-T20). Outbox: `follow_up.sent` held by an approval grant until the 10-s Undo window ends (ADR-161), delivered once by the agents subscriber through `communications.deliver_follow_up`; `follow_up.drafted` from the P-4 tick. Notification kinds (C16, undotted): `follow_up_drafted` (in-app, the engagement's partner and managers; the legacy `reminders.drafted` stays registered for old rows) and `follow_up_sent` (registered; its email is the follow-up itself).

**Consumer tests.** `backend/tests/contracts/c5_requests_binders/test_c5_shl20_family.py` (every route and action, the flags, Idempotency-Key, the agent denies, the C2 verdict enum, no confidence field); behaviour in `tests/integration/test_follow_ups_v2.py`.

