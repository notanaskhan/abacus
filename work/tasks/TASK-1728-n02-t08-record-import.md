---
id: TASK-1728
title: N-02-T08 Record-mode import
spec: N-02 §3.1; docs/contracts/c7-envelopes.md
acceptance_criteria: [N-02-T08]
risk_zone: red
status: in-review
epic: N-02
plan_key: N-02-T08
branch: s14-n02-t08
created: 2026-10-28
updated: 2026-10-28
---

## Objective
`POST /v1/envelopes/import` live: a signed package imported in record mode. Acceptance (backlog
row): "Importing Copperleaf's signed 2026 Close letter stores both files write-once with hashes,
files the copy and emits one envelope.completed naming the importer."

## Plan (red)
- Contract: `POST /v1/envelopes/import/files` (new, `ImportFileOut`), the import route live;
  `make regenerate`; `docs/contracts/c7-envelopes.md` row. DEC-818.
- Migration `0294_envelope_import_files` (down 0293): staged files, consumed once.
- `signatures/imports.py`: `stage_file`, `check_import` (before the idempotency lookup),
  `import_record` (retention, records bucket, one unit of work); `signatures/events.py`
  `EnvelopeCompleted`.
- `evidence/signed_copies.py` via `evidence.api`: `screen_and_stage`, `read_staged`,
  `file_signed_copy` (Signed authorizations, client scope).
- Error codes `retention_floor_missing`, `import_file_unavailable` (409),
  `import_scope_mismatch` (422); audit actions in the reviewed fallback list.
- Rollback: flag `signatures.envelopes` off; revert; downgrade 0294.

## Acceptance
| Check | Test |
|---|---|
| Both files write-once with hashes, the copy filed, one envelope.completed naming the importer | `backend/tests/integration/backfill/test_n02t08_record_import.py::test_ac_copperleafs_signed_letter_is_stored_filed_and_completed` |
| Replay, infected file, another's file, consumed once, no floor, flag off | six tests |

## Progress log
- `2026-10-28` — Built. ruff, pyright, lint-imports clean; `make regenerate`; error codes
  written. Tests written, not run (end-of-batch review).

## Handoff
- **Current state:** PR open, held for the batch, stacked on #589.
- **Next:** N-01-T08.
