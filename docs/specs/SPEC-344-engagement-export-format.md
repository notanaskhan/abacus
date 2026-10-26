---
id: SPEC-344
title: "Engagement export format v1: the binder export package, its manifest and generated JSON schema, the section slot and the export routes"
status: draft
owner: notanaskhan
risk_zone: red
related_adrs: [ADR-004, ADR-031, ADR-036, ADR-042, ADR-052, ADR-104, ADR-139]
related_specs: [SPEC-330]
created: 2026-10-26
updated: 2026-10-26
---

> **Instructions for coding agents**
> - Implement only what this spec describes. Anything not listed here is out of scope.
> - If anything is ambiguous or contradicts an ADR, **stop** and add it to *Open questions*. Do not guess.
> - Every test must reference the acceptance criterion (AC-n) it proves.
> - Solo edition (`docs/plan/AMENDMENT-solo.md`): A-07, Q-04 and G-02 are named reviewers of this format; their review is a reading by the builder, recorded in the task file, not a wait.
> - This spec is ADR-036's "Export format specification" follow-up. The stories are A-01 §3.6 (Stories 6.1 to 6.4); AC numbers below are this spec's. AC-1 to AC-5 are built by A-01-T17 (TASK-1261); AC-6 onward by A-01-T18, T19 and T22.

## 1. Summary
A firm can take any audit engagement's PBC binder out of Accrued as an open, documented package: the evidence files, a request index, provenance records and the audit trail, verifiable with standard tools. This spec fixes package layout, manifest v1 and its JSON schema, the checksum rules, the index columns, the provenance files, the section slot other modules use to add files, and the five export routes. The same format powers the binder export on AUD-02 and AUD-03, Q-04's rollback path, G-02/Q-02's firm export (one package per engagement) and is the base of A-07's archive seal manifest (P-43).

## 2. Problem and context
ADR-036 (accepted) promises portability: firms must keep their documentation independently of any vendor. Until A-07 lands in-app release and archive, Dec-YE reports are issued from the firm's own tool through this export (A-01 §0, M16 fallback), and on the canary the export is the rehearsed rollback path (M9). Today only the `engagement_export` status words exist (A-01-T01).

## 3. Actors
| Actor | Role in this feature |
|---|---|
| Engagement partner, manager (onshore, independence confirmed) | Create, undo, read and download an export with a fresh second factor |
| Staff, firm admin, `client_service`, offshore member, walled member | Refused (403 by role or `offshore`; 404 behind a wall) |
| Client principals | Never reach an export route (INV-4) |
| Agent, system, platform support | Hold none of the export actions (INV-1); the database refuses a non-human `requested_by` (T18) |
| Export workflow (system) | Builds the package after the Undo window; never decides anything |

## 4. Goals and non-goals
**Goals**
- One versioned, documented package format with a generated schema and tests.
- Deterministic packages: the same data, scope and `generated_at` give byte-identical ZIPs.
- Every file verifiable with `shasum -a 256 -c checksums.sha256`.
- Other modules contribute files without `evidence` importing them.

**Non-goals**
- Tax return exports (`export_kind_unsupported` until C19 and a tax-export review).
- The archive seal itself (A-07); the record-mode archive cites an export, it is not a seal.
- Presigned download links (ADR-104: the API streams).

## 5. User stories and acceptance criteria
### Story 1: The stub (A-01-T17)
- **AC-1** Given the API, then `POST` and `GET /v1/work-items/{work_item_id}/exports`, `GET /v1/exports/{export_id}`, `POST /v1/exports/{export_id}/undo` and `GET /v1/exports/{export_id}/download` exist, each declaring one matrix action (`export.create`, `export.read`, `export.read`, `export.create`, `export.download`); create takes a required `Idempotency-Key` and answers 202; download takes `Range` and declares 409 and 410.
- **AC-2** Given the models, then every field is classified (ADR-031), `status` is C2's `EngagementExportStatus`, and the default scope is accepted files with the audit trail.
- **AC-3** Given the matrix, then only the engagement partner and manager hold the three actions, each with `independence: required`; create and download also need `mfa_recent` and `not_offshore`; the agent, system, platform support and client roles are denied.
- **AC-4** Given `audits.binder_export` off, then every route answers 404; on, 501 `not_implemented` until its task lands.
- **AC-5** Given the manifest model, then its JSON schema is generated into `docs/contracts/schemas/engagement-export-manifest-v1.schema.json` (drift fails `make check-generated`), it is closed (`additionalProperties: false`), it pins `format` and `format_version`, the Northwind example validates, and unsafe archive paths, unsorted or self-listing files, miscounted evidence, unaccepted files without the option and foreign index columns are refused.

### Story 2: Create and undo (A-01-T18)
- **AC-6** Given Hannah with fresh MFA and a key, when she creates, then one `engagement_exports` row is `queued` with `not_before = +10 s` and a single-use grant; a retry with the same key returns the same export; `engagement_export.requested` is audited.
- **AC-7** Given Undo inside 10 s, then the grant is voided, the status is `undone`, nothing is built; after 10 s, 409 `undo_window_closed`.
- **AC-8** Given a `tax_return` work item, then 422 `export_kind_unsupported`; given a scope binder id that is not one of the work item's PBC binders, 422 `binder_not_in_work_item` (DEC-379).

### Story 3: The package (A-01-T19)
- **AC-9** Given Northwind after Ana's acceptance, then the ZIP holds §7's layout with 24 index rows and 12 files (3 + 5 + 3 + 1); every evidence file's SHA-256 equals its `evidence_versions` fingerprint; `shasum -a 256 -c checksums.sha256` passes.
- **AC-10** Given the same data, scope and `generated_at`, then two builds are byte-identical.
- **AC-11** Given hostile file names (`=HYPERLINK(...)`, `../../etc/passwd`), then index cells are literal with formula prefixes neutralised and archive paths are normalised (§7.3).
- **AC-12** Given a stored object whose SHA-256 differs from its fingerprint, then the build fails `integrity_mismatch` and nothing is published.
- **AC-13** Given a core section with no registered provider, then the build fails `export_section_missing`.

### Story 4: Download and expiry (A-01-T22)
- **AC-14** Given a ready export and fresh MFA, then the API streams the decrypted ZIP with `Cache-Control: no-store`, resumes with `Range`, and audits `engagement_export.downloaded` with bytes and range.
- **AC-15** Given 7 days on `kernel.clock`, or a withdrawn unaccepted file in the package, then the export is `expired` (`void_reason`), its segments are deleted, and download answers 410 `export_expired`.

## 6. Behaviour and flows
**Happy path**
1. Create (202 `queued`), 10-second Undo window (P-35 grant `not_before`).
2. `EngagementExportWorkflow` consumes the grant, snapshots the selection at one audit sequence (`as_of_seq`), calls every registered section provider, builds the ZIP, seals it in 64 MiB segments, marks it `ready` with hashes, counts and `expires_at = +7 days`.
3. The sheet polls (3 s); the requester gets `export_ready`; download streams.

**State transitions** (C2 `engagement_export`)
| From | Event | To | Who can trigger |
|---|---|---|---|
| — | create | `queued` | engagement partner, manager |
| `queued` | Undo inside the window | `undone` | the requester |
| `queued` | grant consumed | `packaging` | system |
| `packaging` | built and stored | `ready` | system |
| `packaging` | build fails | `failed` | system |
| `ready` | 7 days, or withdrawn content | `expired` | system |

**The section slot.** `evidence.api.register_export_section(name, provider, section_version="1.0")`, once per name at import time. Core names land at fixed paths: `index` (`index.csv`, and the builder renders `index.xlsx` from the same rows), `fulfilments`, `review_decisions`, `screening`, `citations` (`provenance/<name>.csv`). Any other name writes under `sections/<name>/`. Names match `[a-z][a-z0-9_]{1,39}`; `readme`, `manifest`, `checksums`, `evidence` and `audit_trail` are reserved. Providers read at the export's audit sequence, never write, never call a model. A `SectionRequest` names the requester (`requested_by_user_id`, `membership_id`) and the checked binder ids: providers read as that person (`visible()`, walls, independence) and mask Restricted values (TINs, bank accounts) through `kernel.classification.mask` (DEC-379).

## 7. Domain and data changes
### 7.1 Package layout (format `accrued.binder-export`, version 1.0)
```
README.txt                 how to read and verify the package
manifest.json              manifest v1 (canonical JSON: sorted keys, UTF-8, no insignificant space)
manifest.sha256            SHA-256 of manifest.json (sha256sum format)
checksums.sha256           every file except itself and manifest.sha256 (sha256sum format)
index.csv, index.xlsx      one row per request (§7.2)
evidence/NN Category/NN Request title/vN__file
provenance/fulfilments.csv, review_decisions.csv, screening.csv, citations.csv
audit_trail/events.jsonl   identifiers and actor grammar only (DEC-60); when include_audit_trail
sections/<name>/...        registered sections (§6)
```
`manifest.json` lists every file except itself, `manifest.sha256` and `checksums.sha256`, sorted by path. ZIP entries are sorted, timestamps fixed at `generated_at`, no extra fields; the XLSX uses the ADR-042 deterministic pattern.

### 7.2 Index columns (v1, in order)
`category_no, category, request_no, request, status, owed_by, requested_on, due_on, file_count, file_paths, reviewed_by, reviewed_on`. `status` is the request's registry label; a file included by "Include files awaiting review" reads "Uploaded – needs review (not accepted)". Requested rows with no file carry `file_count = 0`.

### 7.3 Archive paths (ADR-052)
NFC; relative; forward slashes only; no empty, `.` or `..` segment; no control or format character (bidi overrides included); no drive prefix; at most 180 characters; duplicates de-duplicated with `~2`, `~3` by the builder. `archive_path_problem` in `evidence/export_manifest.py` is the rule; the manifest refuses any other path.

### 7.4 Manifest v1
The Pydantic model `EngagementExportManifest` (`backend/src/abacus/modules/evidence/export_manifest.py`) is the source; the schema file is generated (`python -m abacus_tools.codegen.export_manifest_schema`). Fields: `format`, `format_version`, `export_id`, `kind` (`binder`, `final_binder`), `generated_at`, `as_of_seq`, `tenant_id`, `firm_name`, `client`, `engagement` (with `work_item_id`, `period_end`), `requested_by`, `requested_at`, `scope`, `counts` (`request_count`, `file_count`, `requests_without_file`), `index_columns`, `sections`, `files` (`path`, `sha256`, `bytes`, `role`, and `evidence` facts or `section` name). Withdrawn (P-31) and voided versions are never listed.

- **Migrations:** none in T17. T18 adds `engagement_exports`, `engagement_export_downloads`, `engagement_export_contents` (A-01 §4.2 M2).
- **Versioning and immutability:** a built package and its manifest are never rewritten; a rebuild is a new export.
- **Retention:** bundles are transient copies (7 days, no Object Lock), not records (P-14); legal holds never block an export.

## 8. Interfaces
| Method / event | Path / name | Purpose | Auth required |
|---|---|---|---|
| POST | `/v1/work-items/{work_item_id}/exports` | Create (`Idempotency-Key`), 202 | `export.create` |
| GET | `/v1/work-items/{work_item_id}/exports` | History, newest first | `export.read` |
| GET | `/v1/exports/{export_id}` | Status and counts | `export.read` |
| POST | `/v1/exports/{export_id}/undo` | Undo inside the window | `export.create` |
| GET | `/v1/exports/{export_id}/download` | The ZIP, `Range` | `export.download` |
| outbox | `engagement_export.requested`, `.ready`, `.failed`, `.expired`, `.undone` | identifiers only | — |

Shapes: `docs/contracts/engagement-export-v1.md`. **Format versioning:** a field a v1 reader can ignore is v1.x (`format_version` stays "1.0" in v1 packages until a v1.1 model and schema file are added beside v1); anything a v1 reader cannot read is v2 with a new model, a new schema file and one release of overlap. The v1 schema file is never rewritten for v2. Changes after the freeze (Fri Apr 2, 2027) are additive (A-01 R14).

## 9. Authorisation and tenancy
- **Tenant scoping:** every read through `tenant_session(ctx)`; the work item resolves through `engagements.api` (404 outside the tenant or behind a wall, INV-3).
- **Who can do what:** §3; download also requires the requester or an `export.create` holder on the engagement (service check, T22).
- **Ethical walls / independence:** `independence: required` on all three actions; walls answer 404.
- **Client-side access:** none (INV-4).

## 10. AI behaviour
N/A: the export performs no model call; screening results are copied as recorded, citation rows only when verified (INV-2).

## 11. Integrations
- **External systems:** S3 exports bucket (Q-01), sealed per segment through `kernel/crypto`.
- **Idempotency:** `Idempotency-Key` on create (ADR-139); the workflow id `engagement_export:<tenant>:<export_id>` rejects reuse.
- **Failure behaviour:** `failed` with `failure_code`; the sheet words it.

## 12. Edge cases and failure modes
- A binder with no accepted files still exports its index (`file_count = 0`).
- A request title or file name in another script: NFC normalised, kept.
- A section provider raising: the build fails `build_error`, nothing is published.
- A download interrupted mid-segment: `Range` resumes; the audit row records each range.

## 13. Security and privacy
- **Data classification:** the package is Confidential client content; Restricted values (TINs) appear only as the client uploaded them inside evidence originals; offshore members cannot export (`not_offshore`, DEC-52).
- **Threats considered:** path traversal and formula injection from client names (§7.3, AC-11); swapped objects (AC-12); a leaked link (no links, ADR-104).

## 14. Audit trail and evidence integrity
`engagement_export.requested`, `.undone`, `.packaged` (counts, bytes, bundle and manifest SHA-256), `.failed`, `.downloaded` (bytes, range), `.expired` / `.voided`. Evidence SHA-256s are checked against stored fingerprints at build.

## 15. Observability
Logs carry export ids and codes only. The RB-29 integrity alarm fires on `integrity_mismatch`.

## 16. Performance and scale
Streams per file with heartbeats; 64 MiB sealed segments; the history page returns at most 50 rows.

## 17. UX
The O3 export sheet (A-01-T24): Queued, Packaging…, Ready ("Download · 12 files · ‹size› · expires Mon Sep 21"), Export failed, Expired, Undone (C2 words).

## 18. Test plan
| AC | Test type | Description |
|---|---|---|
| AC-1 to AC-5 | contract | `backend/tests/contracts/engagement_export/test_engagement_export_v1.py` |
| AC-6 to AC-8 | integration | T18 |
| AC-9 to AC-13 | integration, golden | T19 (`backend/tests/golden/` package) |
| AC-14, AC-15 | integration, time-skipping | T22 |

## 19. Rollout
- **Feature flag:** `audits.binder_export` (off; on for the canary by Fri Apr 16, 2027; retired in the Thu May 27 train).
- **Rollback plan:** flag off; the stub has no data.

## 20. Open questions
- [x] Undo's matrix action: `export.create` (the plan's row); recorded in DEC-376.

## 21. Future / explicitly deferred
- Tax return exports (C19). The A-07 seal manifest extends v1 additively.
