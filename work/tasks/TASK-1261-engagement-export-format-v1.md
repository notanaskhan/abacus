---
id: TASK-1261
title: Engagement export format v1 - SPEC-344, the Pydantic manifest and its generated JSON schema, the export routes stub, register_export_section, matrix rows, audits.binder_export (A-01-T17)
spec: SPEC-344
acceptance_criteria: [AC-1, AC-2, AC-3, AC-4, AC-5]
risk_zone: red
status: in-review
epic: A-01
plan_key: A-01-T17
branch: s9a-contract-stubs
created: 2026-10-26
updated: 2026-10-26
---

## Objective
"The schema is versioned with tests and the stub merges with the flag off and generated client
types" (A-01-T17). ADR-036's follow-up: the export format specification. Today only the
`engagement_export` status words exist (A-01-T01).

## Plan (red zone: contract)
- **SPEC-344** `docs/specs/SPEC-344-engagement-export-format.md`: package layout, manifest v1,
  checksums, index columns, provenance files, path rules, the section slot, determinism,
  versioning; ACs numbered for the stub (AC-1 to AC-5) and for T18/T19/T22 (AC-6 onward).
- **Manifest** `evidence/export_manifest.py` (new): Pydantic v1 (`EngagementExportManifest`),
  frozen, `extra="forbid"`, every field classified; constants `FORMAT`, `FORMAT_VERSION`,
  `INDEX_COLUMNS`, `PROVENANCE_FILES`; the archive-path rule as a validator.
- **Generated schema** `abacus_tools/codegen/export_manifest_schema.py` (new) writes
  `docs/contracts/schemas/engagement-export-manifest-v1.schema.json`; `--check` joins the
  Makefile's `GENERATORS` (so `make check-generated` and `make regenerate` cover it).
- **Section slot** `evidence/export_package.py` (new): `register_export_section(name, provider)`
  with a fail-closed registry (a name once, the reserved names refused); exported from
  `evidence/api.py`. T19 adds the package builder beside it.
- **Routes stub** `evidence/export_contract.py` (new): `POST /v1/work-items/{id}/exports`
  (`export.create`, Idempotency-Key, 202), `POST /v1/exports/{id}/undo` (`export.create`),
  `GET /v1/work-items/{id}/exports` and `GET /v1/exports/{id}` (`export.read`),
  `GET /v1/exports/{id}/download` (`export.download`); 404 with `audits.binder_export` off, 501
  on until T18/T22.
- **Flag** `audits.binder_export` in `feature-flags/assurance.yaml` (owner notanaskhan, off).
- **Matrix** `permission-matrix/evidence.yaml`: `export.create` gains `independence`, explicit
  agent/system/platform-support denies; new `export.read`, `export.download` (A-01 §4.4).
  `fresh-mfa-actions.yaml`: `export.download` in the export group.
- **Closed lists**: `tests/unit/api/test_app_gates.py` (create is 202; undo creates nothing);
  `make regenerate` (route introspection, fresh-MFA overlay, OpenAPI, client).
- **Contract doc** `docs/contracts/engagement-export-v1.md` and its README register row.
- **Tests** `backend/tests/contracts/engagement_export/` (stub gates, schema versioned and
  current, the Northwind example manifest, the section slot).
- **Rollback**: revert the commits and `make regenerate`; no migration.

## Progress log
- 2026-10-26: built. `tests/contracts/engagement_export` 45 passed; the regenerated security
  overlays (route introspection, fresh MFA, permission matrix) pass; `tests/unit/{api,identity,
  quality,kernel}` green apart from validate_docs waiting on SPEC-345 (TASK-1264, same branch).
  `test_independence` MARKED gains the three export actions; support roles hold no export cell
  (SPEC-012 test: any cell, even `deny`, counts as held, so the plan's explicit support deny is
  expressed by absence). tsc clean after `make generate`.
- Not here: the schema file is not yet listed in `.claude/hooks/_protected.py` GENERATED (a
  protected path; add with the next protected bundle). The export sheet's TS fixtures are
  A-01-T24's. DEC-376.
- 2026-10-26 (security review, DEC-379): fix round on the same branch; see DEC-379 for this task's part (H1 preview scoping, M1 send_templated signature, M2 value lint, M3 connection.disconnect, M4 section requester, L1 test-send conditions, L4 support contact).
