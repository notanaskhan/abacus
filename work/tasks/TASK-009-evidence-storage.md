---
id: TASK-009
title: Write-once evidence storage, per-tenant keys, deterministic rendering
spec: SPEC-000
acceptance_criteria: [AC-12, AC-13]
risk_zone: red
status: in-progress
branch: task-009-evidence
worktree:
created: 2026-10-06
updated: 2026-10-06
---

> **Rules for the agent working this task**
> - Read this whole file before doing anything. Continue from the *Handoff* section if it has content.
> - Load only the files listed under *Context to load*, plus what the plan requires.
> - Amber and red tasks: do not write code until the plan is marked approved.
> - If scope must change, **stop** and add it to *Questions for the human*.
> - Never mark `done` until every item in *Definition of done* passes.
> - Append to the *Progress log* before ending any session, even mid-task.

## Objective
Evidence items and versions; write-once object storage (Versity locally, S3 in staging) with Object Lock; per-tenant envelope encryption; SHA-256 fingerprints; deterministic spreadsheet rendering, tested against a fixture ledger snapshot (real snapshots arrive in TASK-010, which owns AC-10); insert-only enforcement in the database. Wrap `boto3.client("s3")` in a typed kernel factory so the one reasoned pyright ignore from TASK-004 lives in one place.

## Scope
In:
- `evidence_items` and `evidence_versions` (insert-only, with a trigger as a second layer);
- write-once, content-addressed, encrypted object storage behind `evidence_storage`;
- per-tenant envelope encryption (`kernel.crypto`);
- the typed S3 factory (`kernel.storage`);
- a deterministic `.xlsx` trial-balance renderer with a provenance footer, tested on a fixture snapshot;
- `evidence.api.add_version` for TASK-010.

Out: fulfilments, retrieval and real snapshots (TASK-010); evidence routes, the board and downloads (TASK-011/012); the AWS KMS key service (TASK-014); retention policies beyond a default and legal holds.

## Context to load
- Spec: `docs/specs/SPEC-000-walking-skeleton.md`
- ADRs: ADR-004, ADR-016, ADR-035, ADR-042

## Plan
- [ ] Plan approved by human (required for amber and red)
- Red task: the agent drafts the design here; the founder edits or approves it before any code, then reviews the diff line by line (founder decision 2026-10-06).

### Design (for founder review)

**1. Storage (`modules/evidence/storage.py`; ADR-016).**
- `put(tenant, content) -> StoredObject(key, version_id, fingerprint, size)`:
  - the fingerprint is SHA-256 of the **plaintext**;
  - the key is `tenants/<tenant_id>/sha256/<fingerprint>`;
  - the object is stored under Object Lock **GOVERNANCE** until `now + evidence_retention_days` (setting, default 2555 days ≈ 7 years);
  - the upload uses `If-None-Match: *`, so an existing key is never overwritten.
- Content-addressed and idempotent: the same content twice → the existing object, verified by fingerprint. A different body under an existing key can't happen by construction; if storage reports a mismatch, that's an integrity error.
- `get(tenant, key, version_id) -> bytes` fetches exactly the recorded version, decrypts it, recomputes SHA-256 and refuses a mismatch.
- If Versity doesn't honour `If-None-Match`, the fallback is head-then-put plus versioning: the DB records the S3 `VersionId` and every read pins it. I'll verify Versity's behaviour first.

**2. Encryption (`kernel/crypto/`; ADR-035). Client-side envelope encryption, the same locally and in AWS.**
- Each object gets a fresh 256-bit data key, then AES-256-GCM.
- The data key is wrapped by the **tenant key** through a `KeyService` protocol: `wrap(tenant, data_key) -> bytes`, `unwrap(tenant, wrapped) -> bytes`.
- The stored object is a small versioned envelope: header (format version, key ID, wrapped key, nonce) followed by ciphertext. The tenant ID and fingerprint are AAD, so an object can't be replayed under another tenant or key.
- Local and test use `LocalKeyService`: tenant key = HKDF-SHA256(`local_master_key` setting, info = tenant ID). It is refused outside local/test.
- AWS uses `KmsKeyService` with one KMS key per firm (TASK-014). Until then, staging and production fail at startup.
- Crypto-shredding still works: destroy the firm's key, and its objects can't be decrypted, including in write-once storage and backups.

**3. Typed S3 factory (`kernel/storage.py`).** `s3_client()` built from settings; the one reasoned pyright ignore from TASK-004 lives here. `boto3` is synchronous, so calls run in `asyncio.to_thread`. The evidence bucket is created with Object Lock enabled (local bootstrap and test fixture; Terraform in TASK-014).

**4. Tables** (migration `0007`; evidence module; ADR-004, ADR-103):
| Table | Columns |
|---|---|
| `evidence_items` | `id`, `tenant_id`, `engagement_id → engagements`, `title` (1–200), `created_by_kind`, `created_by_id`, `created_at` |
| `evidence_versions` | `id`, `tenant_id`, `evidence_item_id → evidence_items`, `version_no` (unique per item, ≥1), `storage_key`, `storage_version_id`, `fingerprint` (64 hex), `size_bytes`, `media_type`; **provenance:** `source`, `method` (`retrieved` / `uploaded`), `pulled_at`, `period_start`, `period_end`, `client_entity_id`, `snapshot_id` (nullable; its FK arrives with ledger snapshots in TASK-010); `created_at` |

- Both tables are tenant tables, with composite FKs that include `tenant_id`.
- `evidence_versions` is **insert-only**: `insert_only` plus `insert_columns`, and it's listed in `INSERT_ONLY_TABLES` and `APP_INSERT_COLUMNS`.
- A trigger (`BEFORE UPDATE OR DELETE … RAISE`) is the second layer and rejects the change even for the owner (AC-13).
- `evidence_items` allows no UPDATE or DELETE either, for now.
- "Superseded" is derived: the highest `version_no` is current. Nothing is ever marked.

**5. Service (`evidence.api`).**
- `add_version(tx, tenant, *, engagement_id, evidence_item_id | new_item_title, content, media_type, provenance, created_by) -> EvidenceVersionRef`:
  - it stores the object **before** the unit of work (content-addressed, so an orphan after a rollback is harmless and reusable);
  - it inserts the rows inside the caller's unit of work;
  - it records `evidence_version.created` (`after`: fingerprint, item);
  - it emits `evidence_version.created` (IDs only).
- The caller authorises (`evidence.upload`; for retrieval that's the system actor in TASK-010).
- `read_version(ctx, version_id) -> bytes` authorises `evidence.read` on the engagement and returns verified plaintext. It's used by screening (TASK-011) and downloads (TASK-012).

**6. Renderer (`evidence/render.py`; ADR-042).**
- `render_trial_balance(tb: TrialBalance) -> bytes` with openpyxl. The input `TrialBalance` dataclass is entity, period, pulled-at, snapshot ID, source and lines (account code, name, debit, credit), defined in evidence for now; TASK-010's ledger maps onto it.
- What makes it deterministic:
  - lines sorted by account code, then name;
  - fixed workbook properties (creator `platform`; created and modified = `pulled_at`);
  - fixed column widths and number formats;
  - no calc chain or volatile cells;
  - the ZIP rebuilt with sorted entries and a fixed timestamp.
- A provenance footer: source, method, pull time, period, entity, snapshot ID and the source-data fingerprint.
- AC-12: rendering the same fixture twice gives identical SHA-256.
- Untrusted text (account names) is written as plain strings. Anything starting with `=`, `+`, `-`, `@`, tab or CR is prefixed with `'`, so no formula injection (AGENTS.md #8).

**7. Static rules.**
- **STORE-001**: `boto3` only in `kernel/storage.py`.
- **CRYPTO-001**: `cryptography` only in `kernel/crypto/`.
- **OWN-001** covers the new tables.

### Questions for approval
- **Q1 — Encryption mode.** ADR-035 says "SSE-KMS per object". I recommend client-side envelope encryption everywhere, recorded as **ADR-104** refining ADR-035:
  - it works identically on Versity (which has no KMS) and S3;
  - the tenant key still lives in KMS in AWS;
  - crypto-shredding is unchanged.
  - The consequence: presigned direct downloads (ADR-016) return ciphertext, so downloads go through the API (authorised, audited, decrypted). That's stronger, at some throughput cost.
  - The alternative is SSE-KMS in AWS and a different mechanism locally, which means two code paths.
- **Q2 — Local tenant keys** come from HKDF over a local master secret (local/test only). The KMS service comes in TASK-014, and AWS environments refuse to start without it. Recommend yes.
- **Q3 — Provenance as columns** on `evidence_versions` (1:1 and immutable) rather than a separate `provenance` table. Recommend columns.
- **Q4 — Default retention:** GOVERNANCE mode, 2555 days, configurable. Per-engagement retention policies and legal holds come later. Recommend yes.
- **Q5 — No evidence routes** in this task (board and downloads in TASK-011/012). Recommend yes.

### Steps
1. Approval file; ADR-104 (if Q1); protect `modules/evidence/**` (hook, CODEOWNERS, protected-paths).
2. `kernel/storage.py`, `kernel/crypto/`, settings (`evidence_bucket`, `evidence_retention_days`, `local_master_key`); local bucket bootstrap; verify Versity `If-None-Match`.
3. Migration `0007` + trigger; `schema_check` maps; `TABLE_OWNERS`.
4. `evidence` storage, service, renderer and api; static rules.
5. Contract → independent test author; two Sonnet reviews; `make check`; PR for founder line-by-line review.

## Definition of done
- [ ] All listed ACs have passing tests that reference them
- [ ] Type check passes
- [ ] Lint and format pass
- [ ] Architecture and dependency rules pass
- [ ] Full test suite passes; no tests skipped, weakened or deleted
- [ ] Security scan passes; no secrets committed
- [ ] No new dependencies, or each one approved and listed below
- [ ] Every query is tenant-scoped; every endpoint checks authorisation
- [ ] AI calls (if any) go through the gateway with limits, logging and passing evals
- [ ] Module README and relevant docs updated
- [ ] Decisions below reviewed; ADR raised where needed

## New dependencies
| Package | Version | Why | Approved by |
|---|---|---|---|

## Progress log
- `2026-10-06` — Created from the SPEC-000 breakdown approved by the founder. Not started.
- `2026-10-06` — Design drafted (§1–7, Q1–Q5) for founder review.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|

## Gotchas and discoveries
- From TASK-005 review: every table passed to `insert_only()` must also be added to `INSERT_ONLY_TABLES` in `schema_check.py`, or the check won't verify it.
- From TASK-006: also declare the app's insertable columns in `APP_INSERT_COLUMNS` and grant them with `insert_columns()`; without a declared list the column check is skipped for that table.

## Questions for the human
-

## Handoff
- **Current state:** Design drafted; awaiting founder approval (red). No code.
- **Exact next step:** On approval, write `work/approvals/TASK-009.yaml` with these paths:
  - `.claude/hooks/_protected.py`, `.github/CODEOWNERS`, `docs/architecture/protected-paths.md`
  - `backend/src/abacus/kernel/crypto/**`, `backend/src/abacus/kernel/db/**`, `backend/src/abacus/modules/evidence/**`
  - `backend/src/abacus_tools/quality/schema_check.py`, `backend/src/abacus_tools/quality/banned_patterns.py`
  - `backend/tests/unit/quality/test_banned_patterns.py`
  - `backend/pyproject.toml`, `backend/uv.lock` (openpyxl, cryptography)
  - `**/*compose*.y*ml` (bucket bootstrap, if needed)

  Then follow the Steps.
