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
