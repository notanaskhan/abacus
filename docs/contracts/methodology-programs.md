# Methodology programs and steps (v1)

| Field | Value |
|---|---|
| Register row | proposed for the register (K-01 §8.2) |
| Version | v1 |
| Status | stub (K-01-T01, 2026-10-26); SPEC-008 template routes live, re-owned by `methodology` (K-01-T02) |
| Provider epic | K-01 |
| Consumers | KNW-02, KNW-03; A-04, A-05, P-07 (pinning), P-10 (`methodology.read_step`, C17), K-03, K-04 (C14), K-05; C4's `methodology_step` verifier |
| Freeze sprint | S16 Contract Monday (Mon May 31, 2027) |
| Flags | `methodology.lifecycle` (submit, approve), `methodology.programs` (programs, steps, drafts, export); `methodology.import_review` and `methodology.importer` reserved for K-01-T18 and T21 (each default off, expires 2027-04-21, DEC-137) |
| Spec | `docs/plan/epics/K-01.md` §3.3 to §3.6, §4.2, §4.3 |
| ADRs | ADR-140, ADR-005 (people approve), DEC-406, DEC-407 |

## 1. Purpose
A methodology version is a firm's audit program: programs, steps with stable anchors (`step_key@v<n>`), levels, mandatory locks, guidance and links to the PBC request list. Versions move through a lifecycle (draft, parsing, needs review, published, superseded, discarded) and published content never changes: edits happen in a new draft. Consumers cite steps by anchor, pin a version by `methodology.api.version_for(tenant, engagement_type, acceptance_date)` (K-01-T06), and read programs for their code plans.

## 2. Who may call it
| Operation | Method and path | Matrix action | Flag | Lands |
|---|---|---|---|---|
| Templates and versions (live) | `GET /v1/methodology/templates?latest=`, `GET /v1/methodology/versions/{id}`, `POST /v1/methodology/templates/{name}/versions?engagement_type=&family=` | `methodology.read`, `.manage` | — (`methodology.programs` reads the Programs and Steps sheets; `methodology.lifecycle` lands the import in Needs review) | SPEC-008; workbook v2 K-01-T05 |
| Blank workbook v2 (live) | `GET /v1/methodology/workbook-template.xlsx` | `methodology.read` | — | K-01-T05 |
| Submit | `POST /v1/methodology/versions/{id}/submit` `{row_version}` | `methodology.manage` | `methodology.lifecycle` | K-01-T06 |
| Approve | `POST /v1/methodology/versions/{id}/approve` `{effective_from, checklist_hash, row_version}` | **`methodology.approve`** (human-only, fresh MFA) | `methodology.lifecycle` | K-01-T06 (live) |
| Lifecycle state | `GET /v1/methodology/versions/{id}/state` → `VersionStateOut` with `checklist [{code, ok, n}]` and `checklist_hash` (additive, K-01-T06) | `methodology.read` | `methodology.lifecycle` | K-01-T06 (live) |
| New draft | `POST /v1/methodology/versions/{id}/drafts` | `methodology.manage` | `methodology.programs` | K-01-T14 |
| Discard | `POST /v1/methodology/versions/{id}/discard` `{row_version}` | `methodology.manage` | `methodology.programs` | K-01-T14 |
| Version programs (additive, K-01-T07, DEC-957) | `GET /v1/methodology/versions/{version_id}/programs` → `ProgramOut[]` in position order | `methodology.read` | `methodology.programs` | K-01-T12 |
| Program | `GET /v1/methodology/programs/{program_id}` | `methodology.read` | `methodology.programs` | K-01-T12 |
| Steps | `GET /v1/methodology/programs/{program_id}/steps` | `methodology.read` | `methodology.programs` | K-01-T12 |
| Resolve a citation | `GET /v1/methodology/steps/resolve?key=&version=` | `methodology.read` | `methodology.programs` | K-01-T12 |
| Edit a draft step | `PATCH /v1/methodology/versions/{id}/steps/{step_id}` (If-Match) | `methodology.manage` | `methodology.programs` | K-01-T14 |
| + Step | `POST /v1/methodology/versions/{id}/programs/{program_id}/steps` | `methodology.manage` | `methodology.programs` | K-01-T14 |
| Remove a draft step | `DELETE /v1/methodology/versions/{id}/steps/{step_id}` (If-Match) | `methodology.manage` | `methodology.programs` | K-01-T14 |
| Mandatory lock | `POST /v1/methodology/versions/{id}/steps/{step_id}/mandatory` (If-Match) | **`methodology.approve`** | `methodology.programs` | K-01-T14 |
| Export | `GET /v1/methodology/versions/{id}/export.xlsx` | `methodology.read` | `methodology.programs` | K-01-T12 |
| Import (live, K-01-T18) | `POST /v1/methodology/imports` `{template_name, engagement_types}` with `Idempotency-Key`; `GET /v1/methodology/imports/{id}` | `methodology.manage` | `methodology.import_review` | K-01-T18 |
| Import file (live) | `PUT /v1/methodology/imports/{id}/files/{role}?filename=` (raw body; `document_docx`, `document_pdf`, `workbook`) | `methodology.manage` | `methodology.import_review` | K-01-T18 |
| Start · cancel (live) | `POST /v1/methodology/imports/{id}/start` · `/cancel` | `methodology.manage` | `methodology.import_review` (+ `methodology.importer` for documents, K-01-T21) | K-01-T18 |
| Source download (live) | `GET /v1/methodology/versions/{id}/files/{file_id}/download` (audited) | `methodology.read` | `methodology.import_review` | K-01-T18 |
| Diff (live) | `GET /v1/methodology/versions/{id}/diff?against=` → `VersionDiffOut` | `methodology.read` | `methodology.import_review` | K-01-T18 |
| Standards mapping (live) | `PUT /v1/methodology/versions/{id}/standards-mapping` `{standards_set_id, quality_management_ref, engagement_types, default_for_new_engagements, row_version}` → `VersionStateOut` | `methodology.manage` | `methodology.import_review` | K-01-T18 |
| Flag resolution (live) | `POST /v1/methodology/versions/{id}/steps/{step_id}/flag-resolution` `{action: confirm·edit, text?, row_version}` | `methodology.manage` | `methodology.import_review` | K-01-T18 |
| Activity (live) | `GET /v1/methodology/versions/{id}/activity` → `ListPage[VersionActivityOut]` | `methodology.read` | `methodology.import_review` | K-01-T18 |

Matrix (`permission-matrix/methodology.yaml`, moved from `engagements.yaml`): `methodology.read` firm admin, practice leader, quality partner, engagement partner, manager, platform support (content), agent `task_scope`; `methodology.manage` firm admin, practice leader, quality partner, fresh MFA, agent and system deny (the plan's `level_in(partner)` waits for K-01-T06, DEC-406); `methodology.approve` quality partner only, fresh MFA, agent and system deny; `methodology.parse` agent `task_scope` only. The plan's widening of `methodology.read` to senior, staff and reviewer waits for the draft/published split (DEC-406).

## 3. Models
`backend/src/abacus/modules/methodology/contract.py`; every field internal.
- **`VersionStateOut`**: `version_id`, `template_id`, `label`, `status`, `effective_from`, `effective_to`, `approved_by_user_id`, `approved_by_name`, `approved_at`, `approval_basis` (`approved`, `legacy_import`), `standards_set_id`, `engagement_types[]`, `default_for_new_engagements`, `drafted_from_version_id`, `row_version`, `allowed_actions[]`; additive since K-01-T18: `quality_management_ref`, `standards_set_code`, `standards_set_label` (read through 0580's SECURITY DEFINER `standards_set_named`).
- **`ProgramOut`**: `id`, `version`, `code` ("BH-EBP-110"), `name`, `position`, `step_count`, `mandatory_count`, `flags_open`, `counts_by_level`.
- **`StepOut`**: `id`, `step_key`, `anchor`, `number`, `text`, `assertions[]`, `standard_refs[]`, `level` (`foundation`, `planning`, `testing`, `completion`), `mandatory`, `lock_note`, `guidance[]` (sanitised blocks: paragraph or ordered list with strong ranges; never HTML), `prepopulates[]`, `depends_on_step_keys[]`, `pbc_positions[]`, `origin`, `parse_flag`, `flag_resolution`, `rules_count`, `row_version`, `allowed_actions[]`.
- **`StepResolveOut`**: `version_id`, `program_id`, `program_code`, `step_id`, `number`, `anchor`.
- Requests: `SubmitVersionIn {row_version}`, `ApproveVersionIn {effective_from, checklist_hash, row_version}`, `StepPatchIn`, `StepCreateIn`, `MandatoryIn {mandatory, lock_note}`.

**Workbook v2 (K-01-T05, DEC-572).** Sheets: `Areas` (`code`, `name`) and `Requests` (`area_code`, `description`, `tier`, then optional `why`, `good_looks_like`, `blocks_fieldwork`, `effort`) required; `Account rules` (`area_code`, `account_from`, `account_to`) optional; `Programs` (`code`, `name`) and `Steps` (`program_code`, `number`, `text`, `level`, optional `step_id`, `assertions`, `standard_refs`, `mandatory`, `lock_note`, `requests`) optional and together, read only with `methodology.programs` on. Columns are found by header name. `level` is Foundation, Planning, Testing or Completion; `mandatory` yes or no and `lock_note` only with it; `assertions` and `standard_refs` `;`-separated short codes; `requests` the Requests rows a step links to (1 is the first). Steps are numbered 1 to n in each program. Problems are `{sheet, row, column, code}` in the 422 validation shape, never a cell: `missing_sheet`, `missing_header`, `empty_value`, `too_long`, `invalid_code`, `duplicate_program`, `unknown_program`, `invalid_number`, `duplicate_number`, `numbering_gap`, `invalid_level`, `invalid_yes_no`, `lock_note_without_mandatory`, `invalid_step_id`, `duplicate_step_id`, `invalid_list`, `unknown_request`, `too_many_rows` (100 programs, 3,000 steps), plus SPEC-008's. Formulas are never evaluated (cached values only), macros never run. **Step keys:** the workbook's `step_id` (lower-cased), else the previous version's key for the same program code and number, else `<program code>-<number>` (unique with a suffix); deterministic, so an anchor survives a re-import. **Landing:** with `methodology.lifecycle` on the version is `needs_review` (no default moves, no effective date) and its `imported` event says so; off, it is published as before.

**Tables (migration 0224, K-01-T05):** `programs`, `program_steps` (the stable `step_key` unique per version, number unique per program, deferrable) and `program_step_pbc_links` (insert-only), all with forced row-level security. `methodology_content_frozen()` refuses any insert, update or delete of a version's programs, steps or links once it leaves draft (needs review, published, superseded, discarded), for every session but the owner's migrations, and share-locks the version's state row so an edit and a publish never interleave (DEC-576); cells that read as formulas or carry control or bidi characters are refused at import (`unsafe_text`, DEC-577); the app may update only a draft step's content columns (never `mandatory` or `lock_note`, the lock being its own human-only act) and delete a draft's step.

**Import review (K-01-T18, migration 0580, DEC-1755).** `MethodologyImportOut {id, template_id, version_id, status (awaiting_files, scanning, parsing, needs_review, failed, cancelled), pages_done, pages_total, failure_code, started_at, files[]}` with `SourceFileOut {id, role, filename, media_type, bytes, sha256, scan_status, created_at}` (never the storage key). A file is scanned and typed before it is kept and written once under S3 Object Lock; a workbook-only import parses now into the next version in Needs review (its event `import_started`); a document import is 409 `importer_not_enabled` until K-01-T21. `VersionDiffOut {version_id, against_version_id, against_label, tiles {added, changed, removed, unchanged}, rows [{kind, program_code, number, step_key, before_text, after_text, changed_fields}]}`: by step key, then by program, number and similar normalised text (≥ 0.8), code only; numbering alone is no change. `FlagResolutionOut {step_id, step_key, parse_flag, resolution, text, row_version}`: an edit keeps the step's source; 0580 lets a version in review take exactly this update. `VersionActivityOut {seq, kind, actor_kind, actor_user_id, actor_name, at, facts}`. Tables: `methodology_imports` (status, version, progress, failure code mutable), `methodology_source_files`, `methodology_source_pages`, `program_step_sources` (insert-only), forced RLS.

**Tables (migration 0180, K-01-T02):** `methodology_version_states` (one per version; the only mutable methodology row), `methodology_version_events` (insert-only), `standards_sets` (global reference data). Legacy versions read `published` with `approval_basis = legacy_import`; until K-01-T06 every import is published the same way and becomes its template's default.

## 4. Status words
`methodology_version` (Draft, Parsing…, Needs review, Published with KNW-02's "Approved", Superseded, Discarded), `methodology_import`, `parse_flag` (`docs/product/status-vocabulary.yaml`).

## 5. Human-only actions
`methodology.approve` (approve a version, change a mandatory lock): the matrix denies agent and system and needs a fresh second factor; the lifecycle row's `approved_actor_kind` CHECK allows only `human`. The agent proposes draft rows for its own import (`methodology.parse`) and never approves.

## 6. Errors
404 (client principal, flag off), 501 until each route lands; the import's 422 workbook problems as above. Live since K-01-T06: 409 `stale_version`, `version_frozen`, `checklist_changed`, `checklist_unmet` (new); 422 `effective_from_too_early` (new). Live since K-01-T14 (drafts, discard, step edits, mandatory lock): 409 `version_not_published`, `draft_exists`, `mandatory_locked`, `step_has_requests` (new); a stale `If-Match` is 409 `stale_version` (the platform's code, not 412; DEC-1361). Live since K-01-T18: approve 409 `flags_open` (a parse flag open) and `unverified_sources` (a source quote not verified on a step no person has confirmed or edited); imports 409 `import_frozen`, `file_exists`, `files_missing`, `importer_not_enabled`, `flag_not_open`; 422 `file_too_large`, `standards_set_invalid`, `against_other_template`, `text_required`, plus the evidence upload refusals (`file_refused`, …).

## 7. Audit and outbox events
Audit (K-01 §4.5): `methodology_import.created`, `.needs_review`, `.parsing`, `.failed`, `.cancelled`; `methodology_source_file.stored`, `.downloaded`; `methodology_step.flag_resolved`; `methodology_version.standards_mapped`; `methodology_version.imported`, `.draft_created`, `.submitted`, `.approved`, `.superseded`, `.discarded`, `.exported`; `methodology_step.added`, `.edited`, `.removed`, `.mandatory_changed`. Outbox: `methodology_version.submitted`, `.approved`, `.superseded {version_id, superseded_by}`. Today's SPEC-008 import keeps `methodology.imported` and writes an `imported` version event.

## 8. Example payloads
`POST /v1/methodology/versions/<v4>/approve`:
```json
{"effective_from": "2027-01-01", "checklist_hash": "sha256:5d1e…07ab", "row_version": 3}
```
`GET /v1/methodology/steps/resolve?key=ebp-110.07&version=<v3>`:
```json
{"version_id": "<v3>", "program_id": "<bh-ebp-110>", "program_code": "BH-EBP-110", "step_id": "<step>",
 "number": 7, "anchor": "ebp-110.07@v3"}
```

## 9. Consumer contract tests
`backend/tests/contracts/k01_knowledge/test_k01_stubs.py` (routes, actions, flags, the human-only rows); `backend/tests/integration/backfill/test_k01t02_methodology_reown.py` and `backend/tests/integration/test_k01t02_methodology_migration.py` (the lifecycle rows).

## 10. Versioning
| Version | Frozen on | Overlap ends | Notes |
|---|---|---|---|
| v1 | (S16, 2027-05-31) | — | stubbed 2026-10-26 (K-01-T01) |

## 11. Open points
DEC-406 (matrix, flags, stubs) and DEC-407 (the re-own as built).
