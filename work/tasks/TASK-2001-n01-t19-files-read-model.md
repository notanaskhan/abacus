---
id: TASK-2001
title: N-01-T19 Files read model
spec: SPEC-380
acceptance_criteria: [AC-25]
risk_zone: red
status: in-review
epic: N-01
plan_key: N-01-T19
branch: s15n-n01-t19
created: 2026-10-29
updated: 2026-10-29
---

## Objective
FIL-01's four routes live behind `files.browser`: the tree with counts under `visible()`, folder
rows with virtual children and superseded versions, the drawer projection with the ADR-024
metadata vs content split, and the access log (N-01 §3.7, §4.3; DEC-1051).

Acceptance (backlog row): "Olivia Brandt sees Ridgeline's 12 documents and 7 virtual children,
and Felix Andersen gets metadata only."

## Plan (red)
- `evidence/files_shapes.py`: the stub's pydantic shapes, moved beside the routes (the read
  model imports them; the routes module imports the read model).
- `evidence/files.py`: the read model. Visibility: engagement-scoped items through
  `visible(evidence.read_metadata)`, client-scoped through `visible_scope(..., "client")` (DEC-33);
  withdrawn versions never show. Work items from `engagements.api.work_item_index()` under
  `visible()`.
- `evidence/files_contract.py`: `_stub` → `_live` (client 404, action, flag); same paths.
- `evidence/models.py`: map `evidence_versions.page_range` (0270).
- `identity/api.py`: export `target_events` (the audit trail's per-target reader slot).
- Stub test: the Files routes join a LIVE set; models read from `files_shapes`.
- No migration, flag, matrix row or audit action.
- Rollback: revert the branch; the routes return to 501 behind the flag.

## Not built here (recorded in DEC-1051)
- The tie to a TB account (DV-13) needs a C9 mapping for the work item: `ties` stays None.
- `register_folder_provider` / `register_folder_badge` slots: no consumer exists before A-07 /
  N-02; deferred to the first consumer (N-02-T17's signed copies).
- Retention readout fields beyond the hold flag, masked TIN and thumbnails: the classification
  (N-01-T08/T12) and previews land with N-01's held and S15 group-B rows.
- Document sign-off slots read empty: no document is a reviewable in N-01.

## Acceptance
| Check | Test |
|---|---|
| 12 documents, 7 virtual, tie total, read-only | `test_ac1_olivia_sees_12_documents_and_7_virtual_children` |
| Metadata only for security admin | `test_ac2_a_metadata_only_viewer_gets_no_content` |
| Superseded kept and struck | `test_ac3_a_superseded_version_is_kept_and_struck` |
| Permanent file beside the years | `test_ac4_the_permanent_file_sits_beside_the_years` |
| Walls, other firms, clients, flag | `test_ac5_walls_other_firms_clients_and_the_flag_hide_everything` |
| Access log | `test_ac6_the_access_log_names_who_did_what` |

All in `backend/tests/integration/backfill/test_n01t19_files.py`.

## Progress log
- 2026-10-29: built (S15 build-now block). Tests written first, not yet run (end review).
  ruff, pyright, lint-imports, banned_patterns clean.
