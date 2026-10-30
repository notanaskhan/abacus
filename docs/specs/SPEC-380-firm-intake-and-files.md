---
id: SPEC-380
title: "Firm intake and Files: channel-agnostic intake, triage, client-scoped files and the read-only Files browser (N-01)"
status: approved
owner: founder
risk_zone: red
related_adrs: [ADR-004, ADR-005, ADR-024, ADR-031, ADR-050, ADR-052, ADR-110, ADR-145, ADR-147, ADR-158, ADR-162, ADR-210]
related_specs: [SPEC-023, SPEC-033]
created: 2026-10-27
updated: 2026-10-27
---

> **Instructions for coding agents**
> - Implement only what this spec describes. The epic in full is `docs/plan/epics/N-01.md`; where this spec and the epic disagree, this spec wins and the difference is listed in §11.
> - Every test names the AC it proves (`test_ac7_...`).
> - ADR-210 (ADR P-60 part 1) binds the intake clauses; ADR-158 (P-40) binds client-scoped files.

## 1. Summary
One front door for documents that do not arrive against a request. A firm-wide **Inbox** is fed by the client portal's "Upload something else" and by staff who log documents received by email, post, fax or in person (**Log received documents…**). Code classifies and flags each attachment, the Accrued Agent may propose a destination, and a named person **files**, **ignores** or **holds** each attachment in the triage sheet. Filing writes an immutable evidence version (or version n+1, which may supersede the earlier one and never deletes it) and moves the request through C5. Alongside it, a read-only **Files** browser shows a client's documents by work item and folder, including client-scoped files (ADR P-40).

Screens: INB-01 Inbox, INB-02 Attachment triage & File-to, FIL-01 Files browser & document drawer (`docs/screens/{INB-01,INB-02,FIL-01}.md`).

## 2. Problem and context
Clients send documents outside requests: a forwarded 1095-C, a corrected 1099, a census sent by post. Today they land in a person's mailbox and are re-uploaded by hand, with no audit trail of who received, matched or filed them. The engagement drop zone (`inbox_files`, SPEC-023) only covers files dropped onto an open engagement. N-01 serves the "receive → match → file → review" step of the tax and audit workflows (blueprint §4 Inbox and Files).

## 3. Actors
| Actor | Role in this feature |
|---|---|
| Intake-team member (e.g. Grace Holloway, Firm Admin) | Holds the firm-level **intake scope** (DEC-20): reads unmatched and unfiled intake, matches senders, logs intake, triages, files into the matched client's non-walled destinations |
| Engagement member (partner, manager, senior, staff, `client_service`) | Reads threads of clients they can read through scope kind `client`; triages and files into their own destinations |
| Holder of `evidence.accept` | Filing by them also records acceptance (two audit events, one person; DEC-37) |
| Firm admin, practice leader without the intake team | Inbox summary counts only; Files metadata only (ADR-024) |
| Security admin | Files metadata and access logs; never content (DV-11) |
| Portal principal (owner, contributor, taxpayer, spouse, plan administrator, trustee) | Uploads intake, lists and withdraws their own uploads while unfiled |
| Accrued Agent | Proposes a destination (matcher, from N-01-T22); never files, ignores, holds, matches or logs |

## 4. Goals and non-goals
**Goals**
- Three intake channels on one model: `portal_upload` and `staff_logged` live, `email` written by the scenario loader on the synthetic tenant and, from N-03, by a registered inbound transport.
- The intake scope as a team of kind `intake` and an `intake_scope` matrix condition (OQ-2).
- Human-only triage at five layers: matrix (`agent: deny`, `system: deny`), service, database `CHECK (actor_kind = 'human')`, I-AGENT-NEVER test, and UI controls owned by people.
- Client-scoped evidence (`client_id NOT NULL`, nullable `engagement_id`), the client read rule and the same-client fulfilment trigger (ADR-158).
- A read-only Files tree, folder lists, drawer and access log.

**Non-goals**
- Microsoft Graph or Gmail ingest, send-as, `.eml`/`.msg` import, INB-03 compose and INB-04 portal threads (N-03).
- Notice and close-receipt destinations (N-04, C-01-T58; the destination slot exists).
- OCR, HEIC conversion, CORRECTED detection and box diffs (P-11).
- FIL-01 writes: upload, move, void, new version, sign-off, lock, client access, accepting virtual splits (proposed Q-05 slice, OQ-6).
- Automatic filing above any confidence (ADR-005), model-drafted client text (DEC-79), SSE (DEC-23).

## 5. User stories and acceptance criteria

### Story 1: Intake from three channels (INB-01, POR-03)
- **AC-1** Given a portal principal with `portal_intake.upload` on a client scope, when they upload up to 20 files (≤ 50 MB each; PDF, JPG, PNG, HEIC, XLSX, DOCX, CSV) with an optional note, then one thread with one inbound message is created (OQ-7), each file is scanned before storage (fail closed: 503 `scanner_unavailable`), stored with a detached key, and the response is `201 {id, status: "sent"}`.
- **AC-2** Given a staff member with `inbox.log_intake`, when they log documents with `received_via`, `received_at`, subject and an optional client, then a thread of `source_kind = staff` is created; without a client it lands unmatched (New) and only the intake scope sees it (OQ-8).
- **AC-3** Given an unsupported media type or a file over 50 MB, then the request is refused with 415 `unsupported_media_type` or 413 `file_too_large` and nothing is stored.
- **AC-4** Given a portal principal, when they list their uploads, then only their own uploads appear, with the client words Sent, Received by ‹firm› and Withdrawn; when they withdraw an unfiled upload it reads Withdrawn and a filed one is refused with 409 `attachment_filed` (ADR-162).

### Story 2: Inbox list, threads and reading pane (INB-01 a, d, f, g)
- **AC-5** `GET /v1/inbox/summary` returns `{waiting, unmatched, by_source[]}` computed from rows the viewer can see; no count includes a walled or hidden item (DEC-43).
- **AC-6** `GET /v1/inbox/threads` filters by source, client, status, received date, channel and `q` (trigram on subject and sender display), sorts by `last_received_at` descending and uses the list envelope with encrypted cursors.
- **AC-7** A thread's message bodies are returned only to a viewer with `inbox.read_content`; others get metadata.

### Story 3: Matching an unknown sender (INB-01 b)
- **AC-8** A thread from an unknown sender is visible only to the intake scope, by sender and subject (ADR-210 clause 3). Matching it to a client moves its attachments New → Waiting; "Remember sender" writes an `inbox_sender_rule`. Nothing from an unmatched sender is ever filed.
- **AC-9** Ignoring an unmatched thread requires a reason code and writes `inbox_thread.ignored`.

### Story 4: Classification and flags (INB-02 a, b, c, g)
- **AC-10** Code classifies form family and tax year from the file name and text layer, and raises the flags `duplicate_hash`, `wrong_year`, `tin_mismatch`, `possible_replacement`, `unreadable`, `low_confidence` and `ambiguous_candidates`. Flag facts hold identifiers, years and masked last-4 only. No model sees an unmasked TIN.
- **AC-11** Every value the matcher sets carries a verified citation or reads "Uncited"; every count, total and tie is computed by code (ADR-050).

### Story 5: Triage decisions (INB-02 a–g, a2)
- **AC-12** `POST /v1/inbox/messages/{id}/triage/apply` writes one insert-only `triage_decision` per attachment (`file`, `ignore` or `hold`) by a live human; agent and system principals get 403.
- **AC-13** Filing writes an evidence version: a new document, version n+1, or version n+1 with supersede (the earlier version is marked superseded, never deleted; ADR-004). "Keep both" leaves both versions as fulfilments (OQ-3).
- **AC-14** A filer holding `evidence.accept` also records acceptance (`evidence.accepted`); otherwise the request reads "Uploaded – needs review" (DEC-37, DV-4).
- **AC-15** Hold with "Tell the client" sends the firm's database template only after a 10-second Undo window, through a single-use approval grant (DEC-24). No model text reaches a client.
- **AC-16** A stale decision answers 409 `proposal_changed`; a destination that closed, archived or was withdrawn answers 409 `item_closed`, `destination_archived` or `attachment_withdrawn`.

### Story 6: Bulk filing (INB-01 e)
- **AC-17** Bulk filing files only unflagged, high-confidence attachments with an unchanged proposal; each other item returns `has_flags`, `low_confidence` or `proposal_changed`.

### Story 7: Files browser, read-only (FIL-01 a–g)
- **AC-18** The tree, folder lists and drawer are served under `evidence.read_metadata`; content fields need `evidence.read`. No write control appears in `allowed_actions` (DV-10).
- **AC-19** The access log lists audit events targeting the item's versions in the actor grammar ("‹person›", "‹person› via Agent", "Accrued Agent").

### Story 8: Client-scoped files (ADR-158)
- **AC-20** `evidence_items.client_id` is NOT NULL; a client-scoped item has no engagement. A user reads it if they can read content on at least one non-walled engagement of that client.
- **AC-21** A fulfilment whose request and evidence belong to different clients is refused by the database trigger `fulfilment_same_client`.

### Cross-cutting
- **AC-22** Walls answer 404 on threads, attachments, files, tree nodes and destinations (INV-3).
- **AC-23** Every decision, match, log, upload, withdrawal, content read, reveal and download writes an audit event (INV-5).
- **AC-24** Each of the four flags off answers 404 on its routes and renders C-20's "This isn't on for ‹firm› yet." state; the Inbox and Files nav items stay.
- **AC-26 FIL-01 on fixtures (N-01-T16).** Ten scenarios render, no write control appears, and the virtual statements foot to 512,400.
- **AC-25 Files read model (N-01-T19; DEC-1051).** Olivia Brandt sees Ridgeline's 12 documents and 7 virtual children, and Felix Andersen gets metadata only; counts run under `visible()` (client-scoped files under the client scope kind), a client-scoped document never names another engagement's request, and walls, other firms and client principals see nothing.
- **AC-27 INB-01, INB-02 and FIL-01 live (N-01-T23).** `/inbox` behind `inbox.firm_intake` (`?thread`, `?ov=file&message` for INB-02's sheet, `?ov=log-intake` for Log received documents, DV-1) and `/files` behind `files.browser`; the rail polls every 10 s and the triage sheet every 2 s while visible (DEC-23); Log received documents logs the batch and then each file, scanned, with the scanner's and the limits' refusals in the design's words; both flags are on for Brightwater Hale in the scenario load (staging and local), and on staging Grace logs, files and ignores live with the audit log naming Grace for every decision.

## 6. Behaviour and flows

**Happy path (portal intake)**
1. Claire Feld uploads two files from POR-03 "Upload something else".
2. The AttachmentTriage workflow scans, extracts, renders previews and masked renditions, classifies by rule and raises flags.
3. The client is known from the portal principal, so attachments move New → Waiting and the intake scope is notified (`inbox_item_received`).
4. Grace opens the thread, presses **File…**, accepts the proposal for one file and ignores the duplicate; Apply writes two decisions, one evidence version and a fulfilment, and notifies the preparer (`document_filed`).

**Alternate paths**
- Staff-logged intake without a client: unmatched, intake scope only, matched by hand.
- Hold: the attachment reads `held` (displayed as the waiting dot with "Asked the client · ‹date›", DV-15); the template email leaves after the Undo window.
- Portal withdrawal while New or Waiting: the attachment reads `withdrawn`, its bytes are purged by `EvidenceWithdrawalPurge` unless a hold applies.

**State transitions** (`inbox_attachments.status`, only through `communications/transitions.py`)
| From | Event | To | Who can trigger |
|---|---|---|---|
| — | received | new | system (intake write by a person or portal principal) |
| new | thread matched to a client | waiting | person with `inbox.match_sender` |
| new, waiting | filed | filed | person with `inbox.file` (live human) |
| new, waiting | ignored | ignored | person with `inbox.triage` |
| new, waiting | held | held | person with `inbox.ask_client` |
| held | filed or ignored | filed, ignored | as above |
| new, waiting | withdrawn | withdrawn | the uploading portal principal or the scope owner |

## 7. Data
Tables and migrations follow `docs/plan/epics/N-01.md` §4.2: `evidence_scope` (N-01-T06), `firm_intake` (T07), `intake_team_kind` (T08), `intake_derivations` (T12), `document_classifications` (T17), `inbox_match_intake` (T22).

**Classification** (ADR-031): `body_sealed`, `reason_note_sealed`, `address_sealed` restricted; `subject_display`, `sender_display`, `file_name`, `issuer_name`, `taxpayer_tin_last4` (masked) confidential; flag `facts` internal; TRI tag on attachments and classifications of clients with a `tax_return` work item. Restricted data is never logged.

## 8. API
The C5 v1.2 intake half and the files-browser contract: `docs/contracts/firm-intake.md` and `docs/contracts/files-browser.md` (N-01-T02). Every POST with an external or client-visible effect takes `Idempotency-Key`.

## 9. Permissions
`docs/architecture/permission-matrix/{communications,evidence,portal}.yaml`, from N-01 §4.4. New condition `intake_scope` (a member of a team of kind `intake`, registered by `organisations` into `identity` through a slot; fails closed when unregistered).

**Human-only actions** (I-AGENT-NEVER and the human-only register): `inbox.file`, `inbox.triage`, `inbox.match_sender`, `inbox.ask_client`, `inbox.log_intake`, `inbox_sender_rule.create`.

## 10. Audit events
`intake.logged` · `inbox_attachment.received` · `portal_intake.uploaded` · `portal_intake.withdrawn` · `inbox_thread.client_matched` · `inbox_sender_rule.created` · `inbox_thread.ignored` · `inbox_attachment.classified` · `inbox_attachment.filed` · `inbox_attachment.ignored` · `inbox_attachment.held` · `evidence_version.created` · `evidence_version.superseded` · `fulfilment.created` · `evidence.accepted` · `message.sent` · `approval_grant.undone` · `inbox_attachment.read` · `evidence_version.read` · `pii.revealed`. Facts carry identifiers and fingerprints only.

## 11. Differences from the epic, and decisions
- ADR P-60 part 1 is **ADR-210**, accepted 2026-10-27 by the builder (AMENDMENT-solo; the epic's "both founders by Apr 30, 2027" is replaced). Part 2 (Graph ingest, send-as) stays with N-03.
- OQ-2, OQ-7 and OQ-8 are decided with the epic's recommendations: DEC-700, DEC-701, DEC-702.
- ADR-158 (P-40) is accepted with N-01-T06 (DEC-705).

## 12. Task plans (N-01-T02 to T30)
| Task | Sprint | What | Zone |
|---|---|---|---|
| T02 | S13 | Contract stubs: models and 501 routes, matrix rows, four flags, error codes, contracts, generated client | red |
| T03 | S13 | Consumer contract tests against the stub | amber |
| T04 | S13 | Glossary and status-vocabulary rows | red |
| T05 | S13 | Screen contracts INB-01, INB-02, FIL-01 | green |
| T06 | S13 | Migration `evidence_scope` (ADR-158) | red |
| T07 | S14 | Migration `firm_intake` and `communications` intake write path | red |
| T08 | S14 | Intake team kind and `intake_scope` condition | red |
| T09 | S14 | Portal and staff-logged intake writes, scan fail closed | red |
| T10–T11 | S14 | INB-01 list and fixtures | green |
| T12 | S15 | AttachmentTriage workflow and intake derivations | red |
| T13 | S15 | Inbox read APIs, home count, notifications | red |
| T14 | S15 | Portal intake routes live | amber |
| T15–T16 | S15–S16 | INB-02 and FIL-01 frontends | green |
| T17 | S16 | Rule classifier, code flags, `document_classifications` | red |
| T18 | S16 | Triage apply, bulk-file, Hold/Ignore emails | red |
| T19 | S16 | Files read model and access log | red |
| T20 | S16 | Independent AC tests (ADR-078) | red |
| T21–T22 | S16–S17 | Matcher v3 eval cases and intake mode | red |
| T23–T30 | S17–S18 | Journeys, parity, pen-test delta, rollout, flag retirement | mixed |

## 13. Open questions
None open. OQ-3 to OQ-6 and OQ-9 to OQ-11 are decided at their own Contract Mondays with the epic's recommendations (§11.2) when their tasks start.
