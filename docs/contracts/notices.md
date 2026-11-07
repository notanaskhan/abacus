# Notices v1 — intakes, notices, analysis, the partner's position and the response

| Field | Value |
|---|---|
| Register row | Screen-family contracts in `docs/contracts/README.md` |
| Owner | notices (N-04) |
| Status | **v1 frozen** (N-04-T27, 2026-11-07): snapshot `backend/tests/contracts/notices/v1.json`, checked by `python -m abacus_tools.contracts --check`; additions pass, a removed or retyped field needs v2 with overlap. Stub N-04-T02 (2026-11-02; DEC-2051); live from N-04-T06 onward |
| Code | `backend/src/abacus/modules/notices/contract.py` |
| Tests | `backend/tests/contracts/notices/` (N-04-T10's consumer suite) and `apps/web/src/screens/NOT-0*/` fixture tests |
| Flags | `notices.workspace` (routes, screens, destinations) and `notices.responder` (every model call); both default off (DEC-2050) |
| Matrix | `docs/architecture/permission-matrix/notices.yaml` (N-04-T01) |
| Consumers | NOT-01, NOT-02, NOT-03; CLI-05 (open notices band), HOME-01 (tile, Your deadlines), HOME-02 (gate kinds), POR-02 (through `portal/home_sources/notices.py`, never these routes), T-08 (`notices.api.notice_facts`), R-03 (`payment_facts_for`), N-03 (`notice_state_for_citation`) |

## Callers
The firm app only. Every route answers 404 to a client principal (INV-4): the client sees the C7
envelope, the payment-confirmation request in the notice binder and the POR-02 info row, each
through its own grant. Agents read only at a run's task scope and write nothing (INV-1).

## Rules
- **People decide.** The position (agree · partially agree · disagree) is P-04's
  `notice_position` decision, reserved to the notice's `signer` function: `POST
  /v1/decision-cards/{id}/decide`. There is no notices decide route. Field confirmations, sent
  records and agency replies are a person's (DB CHECK `recorded_actor_kind = 'human'`).
- **Code computes.** Every comparison, the bracket check, the payment footing and the follow-up
  date come from `notices/compute` with `engine_name`, `engine_version` and `inputs_hash`; the
  browser does no arithmetic; interest and penalty come from the notice and are never recomputed.
- **Nothing renders unverified (INV-2).** Entered return lines, proposed items and agent fields
  each carry a verified citation; an agent field whose citation fails verification is dropped.
- **Walls and visibility (INV-3).** List, summary, detail, intake, activity, home count and search
  read through `visible()`; tallies count visible rows only (DEC-43); 404, never 403, for a
  walled notice.
- **Sealed values.** TINs and confirmation numbers are sealed on write; only `last4` travels.
- **The signed letter never changes** (R-06; QN-4). Edits after send answer 409
  `response_locked`; a correction is a new version before signature.
- **No message to an agency from Accrued.** The person sends through the IRS Documentation Upload
  Tool, fax or mail and records it (`mark-sent`); Accrued never transmits.

## Status words (C2)
`notice` (New · Classified · Analyzing · Response drafted · Approved · Response sent · Awaiting
IRS, "Awaiting agency" on state rows · Resolved · Escalated), `notice_intake` (Extracting · Ready ·
Manual entry · Created · Discarded · Failed), `notice_analysis`, and the derived
`notice_response_readiness`. Tiles (QN-6): New = received; Analyzing = classified + analyzing;
Response drafted = response_drafted + approved; Awaiting IRS = sent + awaiting_irs.

## Operations
| Operation | Method and path | Action | Answers |
|---|---|---|---|
| Notices | `GET /v1/notices?agency=&type=&assignee=&respond_by=7\|30&status=&tile=&client_entity_id=&q=&cursor=` | `notice.read` | 200 list envelope |
| Summary | `GET /v1/notices/summary` | `notice.read` | 200 tiles, types, due ≤ 7, blocked |
| Start an intake | `POST /v1/notice-intakes` | `notice_intake.create` | 202 · 409 |
| Intake | `GET /v1/notice-intakes/{id}` | `notice_intake.read` | 200 |
| Correct or confirm fields | `PUT /v1/notice-intakes/{id}` (If-Match) | `notice_intake.update` | 200 · 409 `stale_version` |
| Create the notice | `POST /v1/notice-intakes/{id}/create` | `notice_intake.confirm` | 201 · 409 `low_confidence_unconfirmed`, `duplicate_unresolved`, `no_client` |
| Attach · discard | `POST /v1/notice-intakes/{id}/attach` · `/discard` | `notice_intake.confirm` | 200 |
| Notice | `GET /v1/notices/{id}` | `notice.read` | 200 with `allowed_actions` and readiness |
| Assign · update | `PATCH /v1/notices/{id}` (If-Match) | `notice.assign` (assignee alone) · `notice.update` | 200 · 409 |
| Start | `POST /v1/notices/{id}:start` | `notice.start` | 200 (received to classified, analysis starts) |
| Return as filed | `PUT /v1/notices/{id}/return-as-filed` | `notice.record_as_filed` | 200 · 409 |
| Proposed items | `PUT /v1/notices/{id}/proposed-items` | `notice.record_as_filed` | 200 · 409 |
| Analysis | `GET /v1/notices/{id}/analysis` | `notice.read` | 200 |
| Run the analysis | `POST /v1/notices/{id}/analysis/run` | `notice.analyze` | 202 (idempotent on `inputs_hash`) |
| Request the decision | `POST /v1/notices/{id}/decision-requests` | `notice.request_decision` | 201 card id |
| Note for the partner | `POST /v1/notices/{id}/notes` | `notice.note` | 201 (insert-only) |
| Activity | `GET /v1/notices/{id}/activity` | `notice.read` | 200 from audit events |
| Draft the response | `POST /v1/notices/{id}/response` | `notice_response.draft` | 201 · 409 |
| Response | `GET /v1/notices/{id}/response` | `notice.read` | 200 blocks, bands, ladder, readiness |
| Edit | `PUT /v1/notices/{id}/response` (If-Match) | `notice_response.edit` | 200 · 409 `stale_version`, `response_locked` |
| Regenerate | `POST /v1/notices/{id}/response/regenerate` (If-Match) | `notice_response.edit` | 200 (template blocks only) |
| Sign off | `POST /v1/sign-offs {target_type: notice_response}` (P-04) | `sign_off.*` | 409 `decision_pending`, `position_mismatch`, `explanation_required` |
| Send for signature | `POST /v1/notices/{id}/response/send-for-signature` | `notice_response.send_for_signature` (+ C7 `envelope.create`) | 201 envelope id |
| Mark sent | `POST /v1/notices/{id}/response/mark-sent` | `notice_response.mark_sent` | 200 · 409 `not_ready` |
| Agency reply | `POST /v1/notices/{id}/agency-replies` | `notice.agency_reply` | 201 |

Every operation answers 404 to a client principal, 404 with `notices.workspace` off, and 501
`not_implemented` until its task (T06 core, T07 intake, T11 analysis, T12 and T16 response).
Creates carry `Idempotency-Key`. The multipart upload variant of `POST /v1/notice-intakes` is
declared with the intake service (N-04-T07, DEC-2051).

## Audit events (identifiers only, ADR-007)
`notice_intake.created|extracted|field_corrected|field_confirmed|attached|discarded`;
`notice.created|assigned|started|respond_by_corrected|return_as_filed_recorded|proposed_items_recorded|analyzed|decision_requested|note_added|position_applied`;
`notice_response.drafted|edited|regenerated|sent_for_signature|ready_to_send|sent|follow_up_scheduled`;
`notice.agency_reply_recorded|resolved|escalated`; on refusals `decision.refused_non_human` and
`ai.boundary_refused`.

## Human-only actions
Confirming an intake field or creating the notice, deciding the position (P-04), the partner's
sign-off, sending for signature, recording the send and recording the agency's reply.

## Contract requests to providers (filed by N-04-T02)
| Provider | Request | Lands with |
|---|---|---|
| P-11 (C4 v1.1) | `GET /v1/evidence-versions/{v}/fields` code fields with confidence and regions; the `notices` form-extraction variant | N-04-T07, T17 |
| N-02 (C7 additive) | `notice_response` envelope policy; page-range documents; `source_ref` on completion events | N-04-T08 |
| P-11 (C11) | `reporting.register_document_kind('notice_response')` with layout `notice_response` | N-04-T12 |
| P-04 (C3) | decision kind `notice_position`; reviewable `notice_response` | N-04-T11, T12 |
| P-04 (C13) | gate kinds `notice_position_decision`, `notice_response_signoff`, `notice_response_send` | N-04-T12 |
| N-01 | triage destinations `notice_intake` and `notice` | N-04-T13 |
| T-03 | answer effect `route_upload_to_notices` | N-04-T13 |

## Pen test 2 scope note
Deferred with every penetration test (DEC-1389). When pen tests resume, the scope adds the
notices routes above, the intake upload path and the `notices.responder` call path; routes landing
after a build cut are retested before the notices flip.
