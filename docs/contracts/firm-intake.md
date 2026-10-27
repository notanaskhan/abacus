# Firm intake: C5 v1.2 intake half (stub)

| Field | Value |
|---|---|
| Register row | C5 (requests and binders), intake half v1.2 |
| Version | v1.2 (intake half) |
| Status | stub (N-01-T02, 2026-10-27); every route 404 with its flag off, 501 `not_implemented` with it on |
| Provider epic | N-01 |
| Consumers | R-01 (POR-03 "Upload something else"), T-02 (TAX-03 "Waiting n"), I-01 (`inbox_waiting` home count), P-11 (classifications), N-02 (signed copies), A-07, N-03 (inbound transport), N-04 and C-01 (destination kinds) |
| Freeze sprint | S15 Contract Monday (Mon May 17, 2027) |
| Flags | `inbox.firm_intake` (firm routes), `portal.intake_upload` (portal routes), `matching.firm_intake` (matcher candidates on the triage read); default off, expire 2027-01-25, DEC-137 |
| Spec | SPEC-380; `docs/plan/epics/N-01.md` §3, §4.3–4.10 |
| ADRs | ADR-210 (P-60 part 1), ADR-162 (withdrawal), ADR-005, ADR-050, ADR-052, ADR-110; DEC-20, DEC-24, DEC-43, DEC-700..703 |

## 1. Purpose
One intake model for documents that arrive outside a request, whatever the channel (`email`, `portal_upload`, `staff_logged`). People file, ignore or hold each attachment; filing writes an immutable evidence version through `evidence.api` and moves the request through C5.

## 2. Who may call it
| Operation | Method and path | Matrix action | Agent or system principal |
|---|---|---|---|
| Summary | `GET /v1/inbox/summary` | `inbox.read` | agent: `task_scope` |
| Threads | `GET /v1/inbox/threads?source&client_id&status&received_since&channel&q&show_ignored&show_filed&cursor&limit` | `inbox.read` | agent: `task_scope` |
| Thread | `GET /v1/inbox/threads/{thread_id}` | `inbox.read` (+ `inbox.read_content` for bodies) | agent: `task_scope` |
| Log received documents | `POST /v1/inbox/intake` → 201 `{thread_id, message_id}` | `inbox.log_intake` | denied |
| One logged file | `POST /v1/inbox/intake/{message_id}/files?filename=` (raw body) → 201 | `inbox.log_intake` | denied |
| Match a sender | `POST /v1/inbox/threads/{thread_id}/match-client` | `inbox.match_sender` (+ `inbox_sender_rule.create` with `remember_sender`) | denied |
| Ignore a sender | `POST /v1/inbox/threads/{thread_id}/ignore` | `inbox.triage` | denied |
| Viewer | `GET /v1/inbox/attachments/{id}/viewer` | `inbox.read_content` | agent: `task_scope` |
| Download | `GET /v1/inbox/attachments/{id}/content`, `GET /v1/inbox/messages/{id}/attachments.zip` | `inbox.download` | denied |
| Triage read | `GET /v1/inbox/messages/{message_id}/triage` | `inbox.triage` | denied |
| Apply | `POST /v1/inbox/messages/{message_id}/triage/apply` | `inbox.file` (+ `inbox.triage` for Ignore, `inbox.ask_client` for Hold) | denied |
| Bulk file | `POST /v1/inbox/attachments/bulk-file` | `inbox.file` | denied |
| Destinations | `GET /v1/destinations?client_id&kind&parent&q` | `inbox.triage` | denied |
| Portal: create upload | `POST /v1/portal/intake-uploads` → 201 | `portal_intake.upload` (`scope_only`) | denied |
| Portal: one file | `POST /v1/portal/intake-uploads/{upload_id}/files?filename=` (raw body) → 201 | `portal_intake.upload` | denied |
| Portal: own uploads | `GET /v1/portal/intake-uploads?scope_kind&scope_id` | `portal_intake.read_own` | denied |
| Portal: withdraw | `POST /v1/portal/intake-uploads/{upload_id}/withdraw` | `portal_intake.withdraw` | denied |

Firm routes: a client principal answers 404, then the action at the firm (403), then the flag (404), then 501. Portal routes: a firm principal answers 404, then the flag, then 501. Every POST with an external or client-visible effect takes `Idempotency-Key`. The intake scope (`intake_scope`, DEC-701) joins the matrix with N-01-T08; until then the firm-level cells are `firm_admin`, narrowed in the service.

## 3. Shapes
Models in `backend/src/abacus/modules/communications/intake_contract.py` and `backend/src/abacus/modules/portal/intake_contract.py`: `InboxSummaryOut`, `InboxThreadRow` (list envelope), `InboxThreadDetail`, `InboundMessageOut`, `InboxAttachmentOut` (status, flags, filed destination, `allowed_actions`), `AttachmentFlagOut` (identifier-only `facts`), `LogIntakeIn`, `IntakeCreatedOut`, `IntakeFileOut`, `MatchClientIn`, `IgnoreThreadIn`, `MessageTriageOut` (`AttachmentTriageOut`, `ClassificationOut`, `DestinationCandidate`, `TriageDefaults`), `TriageApplyIn`/`TriageDecisionIn`/`TriageApplyOut`, `BulkFileIn`/`BulkFileOut`, `DestinationNode`, `ViewerManifestOut`; portal `IntakeUploadIn`, `IntakeUploadOut`, `IntakeUploadFileOut`.

Status words: `inbox_item` (new, waiting, filed, ignored, held, withdrawn), `inbox_thread` (unmatched, matched, ignored), `portal_intake_upload` (sent, received, withdrawn) in `docs/product/status-vocabulary.yaml`.

## 4. Errors
| Status | Code | When |
|---|---|---|
| 409 | `proposal_changed` | a proposal in `seen_proposals` changed since the read |
| 409 | `decision_required` | an attachment has no decision, or a forced Hold was answered otherwise |
| 409 | `has_flags`, `low_confidence` | bulk-filing a flagged or unsure attachment |
| 409 | `item_closed`, `destination_archived` | the destination closed or was archived |
| 409 | `attachment_filed`, `attachment_withdrawn` | already filed; withdrawn by the client |
| 409 | `intake_not_allowed` | a reduced portal shell (third party, K-1, TCWG, prospect) |
| 413 | `file_too_large` | over 50 MB |
| 415 | `unsupported_media_type` | not PDF, JPG, PNG, HEIC, XLSX, DOCX or CSV |
| 503 | `scanner_unavailable` | the scanner is down: every intake path fails closed |

## 5. Module APIs (arrive with their tasks)
`communications.api.record_inbound_message`, `register_inbound_transport` (N-03), `register_intake_destination` (N-04, C-01), `waiting_for_work_item` (T-02); `evidence.api.store_intake_object`, `file_intake_object`, `file_to_folder` (N-02), `register_folder_provider`, `register_folder_badge`, `inbox_waiting_for` v2 (P-06).

## 6. Events
Outbox: `inbound_message.received`, `inbox_attachment.received`, `inbox_attachment.classified`, `inbox_attachment.status_changed`, `inbox_attachment.filed`, `inbox_thread.client_matched`, `portal_intake.withdrawn`. Audit: SPEC-380 §10. Payloads carry identifiers and enums only.
