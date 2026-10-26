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
| Templates and versions (live) | `GET /v1/methodology/templates?latest=`, `GET /v1/methodology/versions/{id}`, `POST /v1/methodology/templates/{name}/versions` | `methodology.read`, `.manage` | — | SPEC-008 |
| Submit | `POST /v1/methodology/versions/{id}/submit` `{row_version}` | `methodology.manage` | `methodology.lifecycle` | K-01-T06 |
| Approve | `POST /v1/methodology/versions/{id}/approve` `{effective_from, checklist_hash, row_version}` | **`methodology.approve`** (human-only, fresh MFA) | `methodology.lifecycle` | K-01-T06 |
| New draft | `POST /v1/methodology/versions/{id}/drafts` | `methodology.manage` | `methodology.programs` | K-01-T14 |
| Discard | `POST /v1/methodology/versions/{id}/discard` `{row_version}` | `methodology.manage` | `methodology.programs` | K-01-T14 |
| Program | `GET /v1/methodology/programs/{program_id}` | `methodology.read` | `methodology.programs` | K-01-T12 |
| Steps | `GET /v1/methodology/programs/{program_id}/steps` | `methodology.read` | `methodology.programs` | K-01-T12 |
| Resolve a citation | `GET /v1/methodology/steps/resolve?key=&version=` | `methodology.read` | `methodology.programs` | K-01-T12 |
| Edit a draft step | `PATCH /v1/methodology/versions/{id}/steps/{step_id}` (If-Match) | `methodology.manage` | `methodology.programs` | K-01-T14 |
| + Step | `POST /v1/methodology/versions/{id}/programs/{program_id}/steps` | `methodology.manage` | `methodology.programs` | K-01-T14 |
| Remove a draft step | `DELETE /v1/methodology/versions/{id}/steps/{step_id}` (If-Match) | `methodology.manage` | `methodology.programs` | K-01-T14 |
| Mandatory lock | `POST /v1/methodology/versions/{id}/steps/{step_id}/mandatory` (If-Match) | **`methodology.approve`** | `methodology.programs` | K-01-T14 |
| Export | `GET /v1/methodology/versions/{id}/export.xlsx` | `methodology.read` | `methodology.programs` | K-01-T12 |

Matrix (`permission-matrix/methodology.yaml`, moved from `engagements.yaml`): `methodology.read` firm admin, practice leader, quality partner, engagement partner, manager, platform support (content), agent `task_scope`; `methodology.manage` firm admin, practice leader, quality partner, fresh MFA, agent and system deny (the plan's `level_in(partner)` waits for K-01-T06, DEC-406); `methodology.approve` quality partner only, fresh MFA, agent and system deny; `methodology.parse` agent `task_scope` only. The plan's widening of `methodology.read` to senior, staff and reviewer waits for the draft/published split (DEC-406).

## 3. Models
`backend/src/abacus/modules/methodology/contract.py`; every field internal.
- **`VersionStateOut`**: `version_id`, `template_id`, `label`, `status`, `effective_from`, `effective_to`, `approved_by_user_id`, `approved_by_name`, `approved_at`, `approval_basis` (`approved`, `legacy_import`), `standards_set_id`, `engagement_types[]`, `default_for_new_engagements`, `drafted_from_version_id`, `row_version`, `allowed_actions[]`.
- **`ProgramOut`**: `id`, `version`, `code` ("BH-EBP-110"), `name`, `position`, `step_count`, `mandatory_count`, `flags_open`, `counts_by_level`.
- **`StepOut`**: `id`, `step_key`, `anchor`, `number`, `text`, `assertions[]`, `standard_refs[]`, `level` (`foundation`, `planning`, `testing`, `completion`), `mandatory`, `lock_note`, `guidance[]` (sanitised blocks: paragraph or ordered list with strong ranges; never HTML), `prepopulates[]`, `depends_on_step_keys[]`, `pbc_positions[]`, `origin`, `parse_flag`, `flag_resolution`, `rules_count`, `row_version`, `allowed_actions[]`.
- **`StepResolveOut`**: `version_id`, `program_id`, `program_code`, `step_id`, `number`, `anchor`.
- Requests: `SubmitVersionIn {row_version}`, `ApproveVersionIn {effective_from, checklist_hash, row_version}`, `StepPatchIn`, `StepCreateIn`, `MandatoryIn {mandatory, lock_note}`.

**Tables (migration 0180, K-01-T02):** `methodology_version_states` (one per version; the only mutable methodology row), `methodology_version_events` (insert-only), `standards_sets` (global reference data). Legacy versions read `published` with `approval_basis = legacy_import`; until K-01-T06 every import is published the same way and becomes its template's default.

## 4. Status words
`methodology_version` (Draft, Parsing…, Needs review, Published with KNW-02's "Approved", Superseded, Discarded), `methodology_import`, `parse_flag` (`docs/product/status-vocabulary.yaml`).

## 5. Human-only actions
`methodology.approve` (approve a version, change a mandatory lock): the matrix denies agent and system and needs a fresh second factor; the lifecycle row's `approved_actor_kind` CHECK allows only `human`. The agent proposes draft rows for its own import (`methodology.parse`) and never approves.

## 6. Errors
404 (client principal, flag off), 501 until each route lands. Planned codes: 409 `flags_open`, `unverified_sources`, `checklist_changed`, `version_frozen`, `mandatory_locked`, `stale_version`.

## 7. Audit and outbox events
Audit (K-01 §4.5): `methodology_version.imported`, `.draft_created`, `.submitted`, `.approved`, `.superseded`, `.discarded`, `.exported`; `methodology_step.added`, `.edited`, `.removed`, `.mandatory_changed`. Outbox: `methodology_version.submitted`, `.approved`, `.superseded {version_id, superseded_by}`. Today's SPEC-008 import keeps `methodology.imported` and writes an `imported` version event.

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
