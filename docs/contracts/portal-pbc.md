# C5 · Requests and binders, section `portal-pbc`: documents, the request sheet, drops and the third-party room

| Field | Value |
|---|---|
| Register row | C5 in `docs/contracts/README.md` (a named section with its own change log, R-01 §8.2 and R11; the other C5 files are `c5-requests-binders.md` and `portal-identity.md`) |
| Version | section `portal-pbc` v1 (additive to C5 v1 and the v1.1 portal half; no C5 version bump) |
| Status | stub (R-01-T01, 2026-10-24); partly live. Every route answers 404 with its flag off. Live with it on: the binder picker, binder and request (R-01-T07, 2026-10-25; DEC-333) and the two undos (R-01-T08, 2026-10-25; DEC-334). Still 501 `not_implemented` with the flag on until their task lands: R-01-T09 (drop, drop poll, void), R-01-T13 (room, suggest) |
| Provider epic | R-01 (portal read models: AY; requests and evidence writes: N), on P-06's binder and request routes and P-08's portal identity |
| Consumers | R-01 (POR-03, POR-04, POR-14), T-02 (POR-05 "upload if yes" falls back to POR-04's upload), C-01 (POR-11 reuses the Request kit rows and the POR-04 `question` slot), A-09 (POR-23 reuses `ScopedRequestRoom` and the room projection), R-03 (mobile capture feeds POR-03 and POR-04), N-03 (INB-04 threads on POR-04 comments), A-01 and P-06 (the firm-side void row-menu) |
| Freeze sprint | with the rest of C5 (S3, freeze Fri 2026-12-11) for the shapes here; R-01-T36 freezes the section |
| Flags | `portal.documents_v2` (portal; owner ayushkbhatia; default off; created 2026-10-24, expires 2027-04-21 under the DEC-137 override; retired by R-01-T18), `portal.drop_sort` (portal; owner notanaskhan; same dates), `portal.third_party_room` (portal; owner ayushkbhatia; same dates) |
| Spec | `docs/plan/epics/R-01.md` §3.1–§3.6, §4.3–§4.8; screen contracts `docs/screens/POR-03.md`, `POR-04.md`, `POR-14.md` |
| ADRs | ADR-139 (P-36 conventions), ADR-140 (P-39), ADR-146 (client access grants), ADR-162 (P-31 withdrawal), ADR-163 (P-11 white label), ADR-005, ADR-031, ADR-050; DEC-24, DEC-58, DEC-59, DEC-63, DEC-139, DEC-240 |

## 1. Purpose
Consumers can rely on the client's view of a binder, a request and a third party's room: rows in client words (To do · Done · Ignored · Returned), receipts that prove what was sent and how, firm-written guidance, the firm's client-visible return note, code-computed category completion and counts, and `allowed_actions` from one closed vocabulary. Nothing in the section carries a firm status code ("Uploaded – needs review", "Received ✓"), an amount, a confidence, a screening verdict, an agent name or reference, or another party's data (INV-4; R-01-T02's consumer tests fail if one appears). A file dropped anywhere is sorted by code: only a decisive match against an item the dropper can see becomes a `rule` fulfilment, which a named person accepts or voids (DEC-58 a, ADR-005). The client may undo an Ignore or Mark as Done until the firm acts (DEC-24), as compensating events. Every client-facing string is firm-written, a fixed word in the frontend copy registry or computed: no model text reaches a client (ADR P-25 off), and nothing says "Accrued" (ADR-163).

**Stub behaviour.** With its flag off a route answers 404; with it on, 501 until its task lands. No route here is unauthenticated (ADR P-45 untouched). The stub returns no fixtures; the screens build on fixture scenarios typed with the generated client (R-01-T05).

## 2. Who may call it
Matrix: `docs/architecture/permission-matrix/portal.yaml` (new `portal_documents.read`); the writes reuse `requests.yaml` and `evidence.yaml` rows.

| Operation | Method and path | Matrix action | Roles allowed | Agent or system principal | Flag · lands with |
|---|---|---|---|---|---|
| Binder picker | `GET /v1/portal/binders?scope_id=` | `portal_documents.read` (`scope_only`) | client admin, client contributor whose grant covers the scope; no firm role | **denied** | `portal.documents_v2` · T07 |
| POR-03 binder | `GET /v1/portal/binders/{binder_id}?filter=requested\|all\|uploaded_by_me\|needs_follow_up&category=` | `portal_documents.read` | as above | **denied** | `portal.documents_v2` · T07 |
| POR-04 request | `GET /v1/portal/request-items/{item_id}` | `portal_documents.read` | as above | **denied** | `portal.documents_v2` · T07 |
| Undo an Ignore | `POST /v1/portal/request-items/{item_id}/ignore/undo` + `Idempotency-Key` | `request_item.ignore` (existing) | client admin (client-visible), client contributor (assigned) | **denied** | `portal.documents_v2` · T08 |
| Undo Mark as Done | `POST /v1/portal/binders/{binder_id}/mark-done/undo` + `Idempotency-Key` | `binder.mark_done` (existing) | client admin (client-visible), client contributor (assigned) | **denied** | `portal.documents_v2` · T08 |
| Drop one file | `POST /v1/portal/binders/{binder_id}/drops?filename=` raw body + `X-Drop-Batch` + `Idempotency-Key` → 202 | `evidence.upload` (existing) | client admin, client contributor (assigned) | system allowed only for connector retrieval, never through this route | `portal.drop_sort` · T09 |
| Poll a drop batch | `GET /v1/portal/drops/{batch_id}` | `portal_documents.read` | the dropper; anyone else's batch is 404 | **denied** | `portal.drop_sort` · T09 |
| Void a rule fulfilment | `POST /v1/engagements/{engagement_id}/fulfilments/{fulfilment_id}/void` `{reason: wrong_request}` + `Idempotency-Key` | `fulfilment.confirm` (existing) | engagement partner, manager, senior | **denied** (human only) | `portal.drop_sort` · T09 |
| POR-14 room | `GET /v1/portal/room` | `portal_documents.read` | today client roles only; a `third_party` grant holds no cell until R-01-T13 (DEC-240) | **denied** | `portal.third_party_room` · T13 |
| Which request? | `POST /v1/portal/room/suggest` `{file_names[]}` | `portal_documents.read` | as the room | **denied** | `portal.third_party_room` · T13 |

Used unchanged (P-06, existing): `POST /v1/portal/request-items/{id}/ignore {reason, note?}` (`request_item.ignore`), `POST /v1/portal/binders/{id}/mark-done` (`binder.mark_done`), `POST /v1/portal/request-items/{id}/upload-intents` (`evidence.upload`), `POST /v1/engagements/{eid}/request-items/{id}/uploads` (`evidence.upload`), `POST /v1/engagements/{eid}/evidence-versions/{vid}/withdraw` (`evidence.withdraw`), `GET`/`POST /v1/engagements/{eid}/request-items/{id}/comments` (`comment.read` / `comment.create`).

**The additive ignore note.** P-06's `IgnoreIn` already carries `note`. R-01 changes only where it goes: R-01-T08 stores it as a shared comment on the request with origin `ignore_note` (sealed, insert-only, ADR-109), so the firm sees it in BND-02 and the thread; Undo never deletes it. No shape changes.

**Third parties (DEC-240).** R-01 §4.3 names a `third_party` role with a `delegated_only` condition on `portal_documents.read`, `evidence.upload`, `request_item.read`, `comment.read` and `comment.create`. T01's check found that neither exists in the matrix grammar (F-03-T24 shipped `scope_only`; DEC-211 leaves third-party grants without cells), so no third party can reach any route today: the room is 404 for everyone but a client role, and its service will refuse those too. R-01-T13 adds the role and the condition with the room read model, in the matrix codegen and `authorise`, and the security cases of R-01-T20 cover them.

## 3. Models
Code: `backend/src/abacus/modules/portal/pbc_contract.py` (reads), `backend/src/abacus/modules/requests/pbc_contract.py` (undos, void), `backend/src/abacus/modules/evidence/drops_contract.py` (drop). Every field is tagged (ADR-031): confidential for titles, file names, notes, guidance, names and organisation names; public for the firm's name; internal for everything else. No Restricted field; no TIN, amount or firm status code.

- **`PortalBinderListOut`** `{items [PortalBinderRefOut {id, title*, year, closed, read_only}], next_cursor, total}` (P-36 list envelope).
- **`PortalBinderOut`** (POR-03): `binder`, `layout ∈ groups|bands` (bands for the audit variant, POR-03 i), `filter`, `categories [PortalCategoryOut {code, label*, complete, requested}]`, `groups [PortalGroupOut {code, label*, category_code, rows}]`, `bands [PortalBandOut {code, label*, rows}]`, `total`, `done_count`, `open_count`, `sorted_count`, `mark_done PortalMarkDoneOut {state ∈ tonal|ready|marked, marked_on, marked_by_name*}`, `other_parties [str*]` (organisation names, admin grants only), `allowed_actions`.
  - **`PortalRowOut`** `{id, engagement_id, title*, kind ∈ request|firm_provided|provided_by_connection, client_status ∈ to_do|done|ignored|returned, files [PortalFileOut], returned PortalReturnedOut?, ignored_on?, due_on?, uploading_count, allowed_actions}`.
  - **`PortalFileOut`** `{id, name*, size_bytes?, receipt PortalReceiptOut {kind, on, by_first_name*?}, withdrawable, struck}`; a withdrawn file is never listed.
  - **`PortalReturnedOut`** `{reason ∈ wrong_year|wrong_period|other, note*?, by_name*, on}`.
- **`PortalRequestOut`** (POR-04): `{id, engagement_id, binder_id, variant ∈ request|question|decision (only request is served), category {code, label*}, title*, client_status, requested_on, due_on?, guidance*? (firm-written only), prior_year {file_name*, sent_on}?, files, returned?, pre_checks [wrong_period|wrong_entity|stale_as_of|totals_dont_add_up], comment_count, uploading_count, allowed_actions}`.
- **`PortalRoomOut`** (POR-14): `{engagement_label*, firm_name, organisation_name*, intro*? (firm-written request guidance), uploaded_count, total, complete, bands [PortalRoomBandOut {code, label*, uploaded, total, rows [PortalRoomRowOut {id, engagement_id, title*, state ∈ uploaded|due|in_review|returned, state_on?, disc ∈ done|ring, guidance*?, files, returned?, comment_count, allowed_actions}]}]}`.
- **`RoomSuggestIn`** `{file_names [1–20 single-line strings, ≤ 255]}` → **`RoomSuggestOut`** `{suggestions [{file_name*, request_item_id?}]}`. File names only, never content; code-only scoring (ADR-050); writes nothing.
- **`DropAcceptedOut`** (202) `{batch_id, file_id}` → **`DropBatchOut`** `{batch_id, binder_id, files [DropFileOut {file_id, file_name*, outcome ∈ rule_linked|waiting|duplicate_flagged|refused (null while sorting), request_item_id?, refusal ∈ file_too_large|type_not_allowed?}], settled}`.
- **`IgnoreUndoneOut`** `{request_item_id, client_status (to_do again; the firm code stays requested), undone_at}`; **`MarkDoneUndoneOut`** `{binder_id, mark_done ∈ tonal|ready, undone_at}` (the binder is published again firm-side). Portal answers carry client words, never the C2 firm code.
- **`FulfilmentVoidIn`** `{reason: wrong_request}` → **`FulfilmentVoidedOut`** `{fulfilment_id, request_item_id, request_status (C2), voided_at}`.

## 4. Status words
Client words only, from `docs/product/status-vocabulary.yaml` `request.client_label`: `requested` → To do; `uploaded` and `received` → Done; `not_applicable` and a client ignore → Ignored; `returned` → Returned; `overdue` derived. The wire carries `client_status` codes (`to_do`, `done`, `ignored`, `returned`), never the firm codes or labels. Receipt kinds: `uploaded` ("You uploaded {date}"), `uploaded_by_other_contact` ("{first_name} uploaded {date}"), `emailed` ("Received by email {date}"), `rule_linked_pending` ("You uploaded {date} · Suggested — {firm} will confirm", DEC-58 a), `received` (accepted by the firm). The `allowed_actions` vocabulary: `upload`, `ignore`, `undo_ignore`, `withdraw`, `mark_done`, `undo_mark_done`, `comment`. The binder's `complete` with the `mark_as_done` context is "Marked done by ‹contact›" firm-side. Words come from the frontend copy registry (ADR P-36 code → words).

## 5. Human-only actions
- **Accept** a version (and so turn a `rule_linked_pending` receipt into `received`): `evidence.accept`, firm roles only; the agent is denied (INV-1, ADR-005).
- **Return** a request or a version to the client: P-06's `request_item.return_to_client`, human only.
- **Void** a rule fulfilment: `fulfilment.confirm`, which denies the agent at the matrix; the route requires a person (`require_live_human` with R-01-T09).
- The code-rule sort itself is not a decision: it runs as `system` with the dropper as `on_behalf_of`, links only on a decisive match among the dropper's visible items, and every link waits for a named person. The agent principal holds `fulfilment.propose` only by task scope, firm-side.
- Client acts (ignore, undo, mark done, withdraw, upload, comment) are a client principal's own; the agent and system are denied every one.

## 6. Errors
Identifier-only facts (ADR P-36).

| Status | Body | When |
|---|---|---|
| 404 | `{"detail": "not_found"}` | the flag is off; a binder, request, batch or room outside the caller's grant, a draft, an internal-only or delegated item, or a forged id (INV-4); one answer for every case |
| 409 | `{"detail": "firm_already_acted", "facts": {"request_item_id" \| "binder_id"}}` | an undo after the firm waived, returned or accepted the request, or returned or sent a request in the binder (DEC-24) |
| 409 | `{"detail": "nothing_to_undo", "facts": {"request_item_id" \| "binder_id"}}` | a second Undo, or an Undo of something never ignored or marked done (DEC-334) |
| 409 | `{"detail": "not_voidable", "facts": {"fulfilment_id"}}` | a void of a human or agent fulfilment, an accepted one, or one already void |
| 409 | `{"detail": "evidence_accepted", "facts": {"version_id"}}` | P-06's withdraw of an accepted or emailed version (unchanged) |
| 413 | `{"detail": "file_too_large", "facts": {"limit_mb": 50}}` | a drop over 50 MB (DEC-58 c) |
| 415 | `{"detail": "type_not_allowed"}` | a drop outside PDF, JPG, PNG, HEIC, XLSX, DOCX and CSV |
| 422 | validation | a bad filter, reason or file-name list |
| 501 | `{"detail": "not_implemented"}` | the flag is on and the task has not landed |
| `consent_required` | firm-side delegation state, not an HTTP error of this section | R-01-T13 refuses a third-party invitation on a `tax_return` work item without the C19 `third_party_disclosure` consent (fail closed, ADR P-12) |

## 7. Audit and outbox events
| Event | Written when | Payload (no Restricted data) |
|---|---|---|
| `request_item.ignore_note_added` (as a shared comment) | an Ignore carries a note (T08) | request item id, comment id |
| `request_item.ignore_undone` (audit and outbox) | the client undoes an Ignore | request item id; actor the contact |
| `binder.mark_done_undone` (audit and outbox) | the client undoes Mark as Done | binder id; actor the contact |
| `portal.drop_received` | a dropped file is stored (T09) | binder id, batch id, inbox file id |
| `portal.drop.sorted` (outbox) | the sort decides | `{version_id, outcome, request_item_id?}` |
| `fulfilment.created` (`created_by_kind = rule`) | a decisive match links | fulfilment id; actor `system`, `on_behalf_of` the dropper (INV-5) |
| `evidence_version.duplicate_flagged` | a drop's SHA-256 matches a version on the engagement | version id, duplicate-of id |
| `fulfilment.voided` (audit and outbox) | a person voids a rule link | fulfilment id, reason code; actor the person |
| `client_invitation.created`, `client_access.granted` | R-01-T13's subscriber on `request_item.delegated` | ids; attributed to the person who delegated |

Values that quote client content (notes, file names) are never stored in `audit_events` (DEC-60). In-app kinds (C16): `portal.drop_unsorted` (binder owner), `third_party.uploaded` (request owner), `binder.marked_done` (P-06; preparer).

## 8. Example payloads
Brightwater Hale seed only (synthetic tenant; ids elided).

`GET /v1/portal/binders/{feld-2025}?filter=requested` as Claire Feld at Mon Sep 14, 2026, 9:24 AM CT (POR-03 a, abridged):
```json
{"binder": {"title": "2025 Binder", "year": 2025, "closed": false, "read_only": false},
 "layout": "groups", "filter": "requested", "total": 21, "done_count": 19, "open_count": 2, "sorted_count": 37,
 "categories": [{"code": "health_medical", "label": "Health & Medical", "complete": false, "requested": 1}],
 "groups": [{"code": "health_insurance", "label": "Health insurance", "category_code": "health_medical",
   "rows": [{"title": "Form 1095-C From Mercer Hill Health", "kind": "request", "client_status": "to_do",
     "files": [], "uploading_count": 0, "allowed_actions": ["upload", "ignore", "comment"]}]}],
 "mark_done": {"state": "tonal"}, "other_parties": [], "allowed_actions": ["upload", "mark_done"]}
```

`GET /v1/portal/drops/{batch}` after Claire's three-file drop (POR-03 c, d):
```json
{"settled": true, "files": [
  {"file_name": "Feld_2025_Estimated_Payments.pdf", "outcome": "rule_linked", "request_item_id": "…"},
  {"file_name": "Feld_2025_IT2105_Confirmations.pdf", "outcome": "rule_linked", "request_item_id": "…"},
  {"file_name": "Scan_0914.pdf", "outcome": "waiting"}]}
```

`GET /v1/portal/room` as Sam Ortiz (Keystone Retirement Services) at Sep 14 (POR-14 a, abridged): `{"engagement_label": "Northwind Robotics 401(k) Plan · 2025 audit", "firm_name": "Brightwater Hale", "organisation_name": "Keystone Retirement Services", "uploaded_count": 4, "total": 9, "complete": false, "bands": [{"label": "Recordkeeper reports", "uploaded": 3, "total": 5}, {"label": "SOC 1 & fees", "uploaded": 1, "total": 4}]}`.

Errors: Claire's Undo after Kevin Osei waived the 1099-B → `409 {"detail": "firm_already_acted", "facts": {"request_item_id": "…"}}`; Kevin voids the accepted rule link → `409 {"detail": "not_voidable", "facts": {"fulfilment_id": "…"}}`; a 51 MB drop → `413 {"detail": "file_too_large", "facts": {"limit_mb": 50}}`.

## 9. Consumer contract tests
- Provider stub tests: `backend/tests/contracts/c5_portal_pbc/test_c5_portal_pbc_stub.py` (R-01-T01).
- Consumer tests on behalf of R-01, T-02, C-01 and A-09: `backend/tests/contracts/c5_portal_pbc/test_c5_portal_pbc_consumers.py` and `apps/web/src/fixtures/contracts/portal-pbc.contract.test.ts` (R-01-T02): client words only, receipt kinds, the `allowed_actions` vocabulary, the room shape; no firm status code, amount, confidence or agent field.

## 10. Versioning
Additive changes in place with a line here. Breaking changes ship beside the old shape for one sprint (see `docs/contracts/README.md`).

| Version | Frozen on | Overlap ends | Notes |
|---|---|---|---|
| portal-pbc v1 | — | — | 2026-10-24: stub (R-01-T01). 2026-10-25: documents reads live (R-01-T07, DEC-333); undos live, Undo open until the firm acts, a second Undo 409 `nothing_to_undo`, another person's 403 (R-01-T08, DEC-334); no shape change |

## 11. Open points
- DEC-240: the `portal_documents.read` spelling, the third-party role and `delegated_only` deferred to R-01-T13, the return reason codes, the drop poll as a read action, and the stub's placement by module owner.
- R-01 §11 OQ-1 (a rule link reads Done to the client with the Suggested line), OQ-2 (Undo until the firm acts) and OQ-8 (who may withdraw a contributor's upload) take the plan's options, as recorded in DEC-240.
