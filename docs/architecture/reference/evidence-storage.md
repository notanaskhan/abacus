# Reference: evidence storage

Write-once storage, fingerprints, per-tenant keys and deterministic rendering (SPEC-000 §22), from the walking skeleton (TASK-009). Binding rules: ADR-004, ADR-016, ADR-035, ADR-042, ADR-104.

## Two steps: stage, then add a version

```python
# before the unit of work: network I/O must not hold a transaction
stored = await stage_content(tenant_id, content)          # evidence.api
async with uow(ctx.tenant) as tx:
    ref = await add_version(tx, engagement_id=eid, item=NewItem("Trial balance"), stored=stored,
                            media_type=XLSX_MEDIA_TYPE,
                            provenance=Provenance(source=..., method="retrieved", pulled_at=...),
                            idempotency_key=key, requested_by=on_behalf_of)
```

- `stage_content` is `storage.put`. Staged content no version references is harmless: it is content-addressed, so the next attempt reuses it.
- `add_version` runs in the caller's unit of work, after the caller has authorised `evidence.upload`. It takes the tenant and actor from the transaction, never from arguments.
- It share-locks the engagement (`lock_ref`, 404 outside the tenant) and refuses an archived one (`EngagementArchived`). It rejects staged content whose key belongs to another tenant.
- It writes `evidence_item.created` (new items only) and `evidence_version.created` audit events, and emits `EvidenceVersionCreated` on the outbox, carrying `requested_by`: the person it was added for, whom agents act for (ADR-025).
- **Idempotency:** a repeated `idempotency_key` returns the existing version (`created=False`) and records nothing. The same key with different content or engagement raises `ValueError`. A retried activity passes a stable key.

## Keys, fingerprints and the object

```python
# modules/evidence/storage.py
def object_key(tenant_id, content_fingerprint):
    return f"tenants/{tenant_id}/sha256/{content_fingerprint}"      # fingerprint = SHA-256 of the plaintext

sealed = await seal(tenant_id, content, digest)                      # kernel.crypto
put_object(..., IfNoneMatch="*", ObjectLockMode="GOVERNANCE", ObjectLockRetainUntilDate=_retain_until())
```

- **Content-addressed:** the same bytes in one tenant are one object; another tenant's identical bytes are a different key and a differently sealed object.
- **Envelope encryption** (`kernel.crypto`, ADR-104): a fresh 256-bit data key and AES-256-GCM per object. The data key is wrapped by the tenant's key through a `KeyService`. The tenant ID, fingerprint and key ID are bound as associated data, so an object opens only as that tenant's, as that content.
  - `LocalKeyService` (HKDF from a local master key) runs only in `local` and `test` against a loopback endpoint. Other environments refuse to start until the KMS service exists (TASK-014).
  - The store never sees plaintext. ADR-104 refines ADR-035's SSE-KMS mechanism and keeps per-firm keys and crypto-shredding.
- **Write-once:** Object Lock in governance mode, and `If-None-Match: *` so an existing key is never overwritten. A lost race loops and verifies what the winner wrote (at most 3 rounds).
- **Reuse is verified:** an existing object is fetched, opened and fingerprinted before it is trusted. A key holding only invalid versions (foreign or corrupt) gets a valid version beside them; the bad ones stay locked and are never referenced. A reused version's retention is extended (governance only extends).
- **Pinned reads:** a version row records `storage_version_id`. `get` reads exactly that `VersionId`, opens it and re-checks fingerprint and size, else raises `IntegrityError`. A `put` response without a real `VersionId` is refused: the bucket must have versioning and Object Lock.
- **Limit:** `MAX_CONTENT_BYTES` (50 MiB, `ContentTooLarge`).
- **Startup:** workers call `check_ready()`, which fails unless the bucket has Object Lock enabled.

## Reading

```python
content = await read_version(ctx, version_id)         # authorise evidence.read, audit evidence_version.read, then storage.get
content = await read_content(tenant, version.stored)  # callers already authorised under their own context (workflows)
view = await version_view(tenant, version_id)         # metadata only; NotFound outside the tenant
```

- Request handlers use `read_version`: it authorises against the engagement, records `evidence_version.read` (ADR-104), then returns verified plaintext. A missing or foreign version is `NotFound`.
- `evidence_versions_for(ctx, engagement_id)` backs `GET /v1/engagements/{id}/evidence-versions`: authorise `evidence.read`, list through `visible()`. Provenance only (method, source, period, version number), never content, keys or fingerprints.
- Downloads go through the API, never presigned URLs: objects are ciphertext.

## The database guarantees

- `evidence_versions` (migration 0007): the app role has column-limited INSERT and no UPDATE or DELETE. A trigger rejects UPDATE, DELETE and TRUNCATE for every role, owner included. There is no "superseded" flag: the highest `version_no` is current.
- Constraints keep rows honest: `storage_key = 'tenants/' || tenant_id || '/sha256/' || fingerprint`, a 64-hex fingerprint, `(tenant_id, evidence_item_id, version_no)` unique, a `retrieved` version has `pulled_at`, and `period_end >= period_start`.
- Migration 0008 adds `idempotency_key` (unique per tenant when set); its downgrade refuses while any version exists.
- A new column needs `insert_columns` extended in a new migration, or the app can't write it.

## Deterministic rendering

```python
# modules/evidence/render.py
CODE_COLUMN, NAME_COLUMN, DEBIT_COLUMN, CREDIT_COLUMN = 1, 2, 3, 4
FIRST_LINE_ROW = 2
TOTAL_LABEL = "Total"
```

- Identical data gives a byte-identical file (ADR-042): lines sorted by code then name; fixed creator, and created and modified set to the pull time; the ZIP rebuilt with fixed entry times, attributes and compression. Naive datetimes are refused (output would vary by host).
- Client text is hostile: `_text` writes every string with `data_type = "s"` and a quote prefix on a leading `=`, `+`, `-` or `@`. Never formulas. Over-long cells and non-finite amounts raise.
- Totals are computed in code (ADR-050), not by sheet formulas. A provenance footer (source, method, pulled at, period, entity, snapshot, source fingerprint) follows the Total row.
- The layout constants are exported from `evidence.api` and shared with readers (`agents.citations`). Change the layout and the readers change together, or screening refuses the sheet.

## Rules

- STORE-001: only `kernel.storage` (`s3_client`, `error_code`, `StorageError`) touches boto3; classify errors with `error_code`, never botocore.
- CRYPTO-001: only `kernel.crypto` imports `cryptography`.
- Stage before the unit of work; never put network I/O inside one.
- Never update or delete evidence: add a version. Reading evidence content is audited.
- Local runs create the bucket with `python -m abacus_tools.local.evidence_bucket`, which refuses a bucket without Object Lock and runs only in `local` and `test`. In AWS, Terraform creates it (TASK-014).
- Tests point storage at their own bucket with `configure_storage(client, bucket)` and tear down with `reset_storage()`.

## Not yet
- The KMS key service and per-firm KMS keys (TASK-014); AWS environments refuse to start without them.
- Uploads (the 50 MiB cap is a placeholder).
