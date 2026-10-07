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

## Rules
- **Versions are insert-only.** The app has no UPDATE or DELETE privilege, and a trigger rejects UPDATE, DELETE and TRUNCATE for every role (AC-13). There is no "superseded" flag: the highest `version_no` is current.
- **Storage** (`storage.py`):
  - the key is `tenants/<tenant>/sha256/<SHA-256 of plaintext>`;
  - each object is sealed with a per-object data key wrapped by the firm's key (ADR-104);
  - objects are kept under Object Lock in governance mode and are never overwritten (`If-None-Match`);
  - reads pin the recorded `VersionId` and re-verify the fingerprint.
- **Downloads** go through the API, never presigned URLs: objects are ciphertext (ADR-104).
- **Account names** in rendered files are always written as strings, never as formulas.
