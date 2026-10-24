# evidence

Evidence items and their immutable versions (glossary; ADR-004). Owns `evidence_items` and `evidence_versions` (ADR-103). PROTECTED.

## Public interface (`api.py`)
- `stage_content(tenant_id, content) -> StoredObject`: seals and stores the bytes write-once under their fingerprint, before (and outside) the unit of work that records them.
- `add_version(tx, *, engagement_id, item, stored, media_type, provenance, idempotency_key=None, requested_by=None) -> EvidenceVersionRef`:
  - runs inside the caller's unit of work, after the caller has authorised `evidence.upload`; the tenant and actor are the transaction's own;
  - `item` is an existing item ID or `NewItem(title)`; `stored` comes from `stage_content`;
  - adds version `n+1`; an `idempotency_key` already used returns that version (`created=False`) and records nothing;
  - audit events: `evidence_item.created` (for a new item) and `evidence_version.created`;
  - outbox event: `evidence_version.created`, carrying `requested_by`: the person the version was added for, the initiator of agents acting on it. A retrieval passes its `on_behalf_of`; the default is None.
- `read_content(tenant, stored) -> bytes`: the decrypted, fingerprint-verified content, for a caller that has authorised under its own context (e.g. an agent's `evidence.read`). `check_ready()` verifies the bucket at boot.
- `version_view(tenant, version_id) -> EvidenceVersionView`: a version's metadata, including storage, snapshot and period, for a caller that has authorised under its own context.
- `read_version(ctx, version_id) -> bytes`: authorises `evidence.read` on the engagement, then returns the decrypted, fingerprint-verified content. A missing version, or another firm's, raises `NotFound`.
- `router`: `GET /v1/engagements/{id}/evidence-versions` (`evidence.read`).
  - Returns the engagement's versions, oldest first, through `visible()`.
  - Provenance only: method, source, period and version number. Never content, keys or fingerprints.
  - `evidence_versions_for(ctx, engagement_id)` is the service behind it.
- `render_trial_balance(TrialBalance) -> bytes`: deterministic `.xlsx` with a provenance footer (ADR-042).
- Layout constants for readers of the rendered sheet: `CODE_COLUMN`, `NAME_COLUMN`, `DEBIT_COLUMN`, `CREDIT_COLUMN`, `FIRST_LINE_ROW`, `TOTAL_LABEL`.

## Review queues and decisions (SPEC-004; TASK-019)
- **The queue** (`GET /v1/engagements/{id}/review-queue`, `review.read`): per request item, its newest fulfilled version without a decision. Order: proposals needing revision first, then lowest confidence, then oldest. Each entry shows the agent's proposal. A version fulfilling several items is queued once.
- **Taking** (`…/review-queue/{version_id}/take`, `release`, `assign`): advisory (Q3), and every change is audited (`review.taken`, `review.released`, `review.assigned`). Taking is one statement, so two first takes can't both win; someone else's item answers 409 `already_taken`. Assignments are always scoped to the route's engagement. Release and reassign need `review.assign` for another person's item. The assignee must be on the engagement's team.
- **Deciding** (`…/evidence-versions/{version_id}/decision/accept` with `evidence.accept`; `…/reject` and `…/send-back` with `evidence.reject`): one route per matrix action. The body carries `seen_proposal`: if the agent's proposal changed since, the answer is 409 `proposal_changed`.
  - **One save:** the decision is one unit of work, and every read happens inside it. It locks the version's items (`requests.review_targets`), so a new fulfilment waits. The row is insert-only (`review_decisions`), audited `review_decision.created`. It moves every item the version fulfils (accept → `accepted`, reject → `open`, send back → `needs_revision`) and clears the assignment.
  - **Conflicts:** 409 `already_decided` or `superseded`.
  - **Reason codes:** a reason code is required for reject and send back, and refused for accept. An invalid code answers 422 `invalid_reason_code`.
  - **Correction flag:** `corrects_proposal` is set when the decision disagrees with the agent's latest proposal.
- **Undo** (`POST …/review-decisions/{decision_id}/undo`, `review_decision.undo`; P-01-T13, DEC-24, ADR-161, DEC-214): within 10 s on `kernel.clock`, by the person who decided, who must still hold the decision's own action. It writes a compensating `undone` row (`undoes_decision_id`, the next `decision_seq`); the original is untouched. The version's items go back to `uploaded` (`request_item.status_changed` emitted), audited `review_decision.undone`. Later, a second Undo, or once decided again: 409 `undo_window_closed`. Decisions take odd `decision_seq` numbers and undo rows even ones; the **effective decision** is the highest row when odd, and every read (queue, item versions, run trace) uses it. Migration 0117's trigger checks the same rules. `undo_review_decision(tx, …)` in `api.py` is the in-unit-of-work entry for P-04-T29.
- **Only a person decides (ADR-005):**
  - `decide` takes an `AuthContext` and refuses outside a live API request (`serving_request()`), so a worker or agent holding a person's context still can't decide;
  - the matrix denies agents;
  - the database binds the row to the session's actor and CHECKs `actor_kind = 'human'`;
  - REVIEW-001 lets only `evidence/service.py` and `evidence/routes.py` name `decide`.
- **Proposals come from agents by registration** (`register_proposal_source`, TASK-019 D1): agents depends on evidence, not the other way round. Unregistered, the queue shows none and decisions answer 503.
- **The reason-code catalogue** (`review_reason_codes`) is platform-wide with no app privileges. It is listed through `review_reason_codes_list` (`GET …/review-reason-codes/{reject|send_back}`) and enforced by an insert trigger, both SECURITY DEFINER. The note is confidential and never logged.

## Rules
- **Versions are insert-only.** The app has no UPDATE or DELETE privilege, and a trigger rejects UPDATE, DELETE and TRUNCATE for every role (AC-13). There is no "superseded" flag: the highest `version_no` is current.
- **Storage** (`storage.py`):
  - the key is `tenants/<tenant>/sha256/<SHA-256 of plaintext>`;
  - each object is sealed with a per-object data key wrapped by the firm's key (ADR-104);
  - objects are kept under Object Lock in governance mode and are never overwritten (`If-None-Match`);
  - reads pin the recorded `VersionId` and re-verify the fingerprint.
- **Downloads** go through the API, never presigned URLs: objects are ciphertext (ADR-104).
- **Account names** in rendered files are always written as strings, never as formulas.

## Client uploads (SPEC-020; TASK-035)
`uploads.py`; routes `POST`/`GET /v1/engagements/{id}/request-items/{item_id}/uploads`.
- **Upload:**
  - takes the raw body and the query `filename`;
  - authorises `evidence.upload` with the item's facts before reading the body;
  - limits: 25 MB; types judged by the leading bytes (PDF, PNG, JPEG, OOXML xlsx/docx, OLE xls/doc, UTF-8 CSV); the same SHA-256 on the item twice is refused;
  - stores a new evidence item titled with the cleaned file name, whose first version has provenance `uploaded` / `client_upload`, links it, audits `evidence.uploaded` and emits `EvidenceUploaded` (which notifies the firm team).
- **Never opened:** no file is opened, parsed or rendered; file names are plain text only.

## Request item detail (SPEC-021; TASK-037)
`item_detail.py`, firm-side only (client roles are refused here, Q4).
- **`GET …/request-items/{item_id}/versions`** (`evidence.read`): the item's versions, newest first. Each has its provenance; for uploads, the file name and uploader; and its decision on this item.
- **`GET …/evidence-versions/{version_id}/content`** (`evidence.read`): the bytes, through `read_version` (authorised, audited `evidence_version.read`, fingerprint-verified).
  - Served as an attachment with an ASCII-safe name, `nosniff` and `no-store`; never inline.
  - A verification failure is a 409 `integrity_failed`, logged.

## Board summary (SPEC-022 AC-5; TASK-038)
`GET …/board-summary` (`request_item.read`):
- counts by status and tier, and how many are unclassified;
- "retrieved, never asked": items whose first fulfilling version was retrieved;
- the retrievable share (A to C over classified items).

## Uploads on behalf and the inbox (SPEC-023; TASK-039)
- **On behalf:**
  - the upload route's `on_behalf` (the firm's team only, 409 `not_staff` otherwise) records source `firm_upload_for_client` and an optional note in `evidence_versions.upload_note`, written once;
  - clients see it as added by their auditor.
- **Inbox** (`inbox.py`, table `inbox_files`): files dropped at the engagement level, stored once with the SPEC-020 checks. One waiting copy per fingerprint.
  - **Who sees what:** staff see every file, client admins see the clients' files, contributors see their own.
  - **Assign:** `uploads.attach` (the per-item path: re-authorise with the item's facts, refuse closed items and duplicates, add the version, link it, emit `EvidenceUploaded`), then the row becomes `assigned`, audited with `followed_suggestion`.
  - **Discard:** the uploader or staff.
- **Matching** (`matching.py`): file-name words against item descriptions, plus a bonus when both match the same classification rule; at most three suggestions scoring at least 35. Computed on read from the items the reader can see. The file itself is never opened.

## Acceptance files and signed letters (SPEC-025; TASK-044)
`setup_files.py`:
- **Upload:** `POST …/acceptance/file` and `…/letter/file`, with the SPEC-020 checks; stored write-once, and the reference attached to engagements' records.
- **Download:** `GET …/{acceptance|letter}/file` (`setup.read`) as an attachment, audited and verified.

## Imported evidence (SPEC-028; TASK-052)
- Provenance method `imported` (an uploaded ledger export run through the pipeline); it needs a pull time. `TrialBalance` takes `method` and footer `notes`.

## Upload processing (SPEC-029; TASK-054)
- **Scanning (AC-1):** `uploads.checked` scans every upload with `kernel.scanning` (item uploads, inbox files, setup files). `screened` audits a refusal (`upload.refused`, size only); nothing is stored.
- **Workflow:** `processing.py` subscribes to `evidence.uploaded` and `inbox_file.added` and, with the firm's `uploads.processing` flag on, starts `upload_processing` (`upload:<tenant>:<kind>:<id>`, interactive). Its activity `upload.extract` runs `process_upload`.
- **Extraction (`extraction.py`, `document_fields.py`):** in a child process (`kernel.isolation`); PDFs via pdfplumber (scanned and encrypted are `unreadable`), XLSX cached values only, CSV in UTF-8 or Windows-1252; bank statement and aging fields by general labels. Never alters the evidence.
- **Record:** `upload_extractions` (insert-only), one per upload and extractor version; the full extraction is a JSON object in storage, the fields checks need are columns (TASK-055).
- **Dependencies:** identity, engagements, requests (unchanged). The worker hosts evidence (`worker.MODULES`).
- **Checks (TASK-055):** the workflow's v2 step `upload.check` (`patched("checks")`, evidence versions only) runs `checks.py` (unreadable, duplicate, and per document kind: stale, wrong period, wrong entity, totals) and `cross_checks.py` (firm only: bank closing balance against its cash account; aging total against its control accounts) into `upload_checks` (insert-only). Changing an item's document kind re-checks its latest upload. `GET …/request-items/{item}/uploads/{version}/checks`: client roles get client-audience checks only.
- **Dependencies:** evidence may read ledger snapshots (TASK-055 D2).
- **Previews (TASK-056):** the workflow's v3 step `upload.preview` (`patched("previews")`) renders in the isolated child (`previews.py`: PDF pages with pypdfium2, images re-encoded with Pillow, metadata dropped; spreadsheets served from the extraction) into `upload_previews` and `upload_preview_pages` (content-addressed PNGs). Every new evidence version is processed (pipeline workbooks too, D1). Routes: `…/request-items/{item}/uploads/{version}/preview` (+ `/pages/{n}`) and `…/inbox/{file}/preview` (+ `/pages/{n}`); pages are PNG, `no-store`, `nosniff`. `typings/pypdfium2` holds the stub strict typing needs.
- **Client view (SPEC-031; TASK-060, `client_view.py`):** `GET …/request-items/{item}/client-view` (`evidence.read` with the item's client facts): `provided` (newest version retrieved → `connection`, imported → `export`, with its date); `gap` for bank statement items (cash accounts in the year-end trial balance against the last four digits of uploads not sent back or rejected; accounts without digits are named and take unmatched statements; none without a trial balance or cash accounts); `history` newest first (firm or client uploader, outcome `in_review`, `replaced`, `accepted`, `sent_back` with reason label and note, `not_accepted` without a note).
- **Content matching (SPEC-033; TASK-064, `matching.py`):** inbox suggestions also score what the extraction read (columns only): kind (+50; statements match bank statement requests, agings match AR and AP alike), the year end (+20), account digits still needed per SPEC-031's gap or in the description (+30), the account holder (+10), plus the file-name score × 0.4. Each suggestion has `source` (`content` or `file_name`) and fixed-code `reasons`; unextracted files keep the file-name score. The gap helpers (`covered_digits`, `year_end_cash`) are shared with the client view. Assignments audit `suggestion_source` (1 file name, 2 content, 3 matcher) and `suggestion_rank`.
- **Match material (SPEC-033; TASK-065, `match_material.py`):** for the matcher: an inbox file's extraction (excerpt and full text for citation checks) and its candidates, the uploader's assignable open requests scored by the content rules (`score_all`), at most 60, with `worth_matching` from the skip rule (`should_match`: code's top is at least twice the next and matched on kind plus date or account).
- **Matcher picks (SPEC-033; TASK-066):** `inbox_file.extracted` follows an inbox file's extraction. Agents registers `register_match_picks`; the inbox listing merges the matcher's shown picks first (`source: matcher`, no reasons, only requests the person may assign), then code's suggestions, at most three. Assignments accept `suggestion_source: matcher`.
- **General ledger workbooks (SPEC-034; TASK-070, `render_gl.py`):** streaming, deterministic (`render._normalised`): the general ledger ("Reconciliation" then "Detail", "Detail (2)", … before Excel's row limit) and the journal listing (one block per transaction by date, type and reference, or date, type and name; unbalanced blocks marked). Text is never a formula. At 760,000 lines: 24 MB and 29 MB.
