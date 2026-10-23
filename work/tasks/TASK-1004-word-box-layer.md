---
id: TASK-1004
title: Word-box layer — UploadProcessing patched step `words` (pdfplumber extract_words in the isolated child), sealed per-page layers and evidence_pages rows, v4 replay history, idempotent trust_layer_backfill workflow (P-03-T05)
spec: SPEC-322
acceptance_criteria: [AC-1, AC-3, AC-32]
risk_zone: red
status: done
epic: P-03
plan_key: P-03-T05
branch: s6-citations
created: 2026-10-24
updated: 2026-10-24
---

## Objective
"Every text-layer page of a new upload gets word boxes in page points, the v1-v3 histories still replay, and the evidence bytes and fingerprint are unchanged" (P-03-T05). The layer is what P-03-T06's `document_text` verifier hashes, T09's search scans and T13's PII detector reads.

## Plan (red zone)
- **Code (evidence, protected):**
  - new `evidence/words.py`: `WORDS_VERSION = "w1"`; `extract_words(content, media_type)` (pdfplumber `extract_words`, first 200 pages, 5,000 words a page, control and format characters dropped, coordinates in page points, top-left origin, rounded to 0.01) and `extract_words_isolated` (`kernel.isolation.run_isolated`; a crash or a hang is `unreadable/crashed`, never a worker failure); `words_upload(given)` (the activity body: idempotent on source × `WORDS_VERSION`, reads only PDFs, writes one sealed layer object per text page through `storage.put` (ADR-104 per-tenant key, content-addressed) and one `evidence_pages` row per page in one unit of work, audited `upload.words_extracted`); `read_page_layer(tenant_id, page)`; `pending_words(given)` and `start_trust_layer_backfill(tenant_id)`.
  - `evidence/workflows.py`: v4 `workflow.patched("words")` after previews, activity `upload.words`; new `TrustLayerBackfill` (`trust_layer_backfill`, `background`): batches of 50 by id cursor (versions, then inbox files), `continue_as_new` while a batch is full.
  - `evidence/workflow_types.py`: `BackfillInput`. `evidence/activities.py`: `upload.words`, `trust_layer.pending_words`. `evidence/models.py`: `EvidencePage`. `evidence/repository.py`: `pages_of`, `insert_pages`, `sources_without_words`. `evidence/processing.py`: `WORKFLOWS` gains the backfill. `evidence/api.py` exports.
- **Tooling:** `abacus_tools/workflows/record_upload_processing.py` stubs `upload.words` and names v4 `upload-processing-v4-words.json`; new `abacus_tools/workflows/record_trust_layer_backfill.py`; new operator command `abacus_tools/trust_layer_backfill.py <tenant>` (starts the workflow through `evidence.api`; DISPATCH-001). The backfill runs on staging as an ECS one-off task, never from a laptop (P-03 §4.5).
- **Histories:** `upload-processing-v4-words.json`, `trust-layer-backfill-v1-done.json` (recorded, never re-recorded).
- **Migration 0119** (`word_layer_size`): `evidence_pages.text_layer_size` (storage opens an object only against its recorded size; 0109 had no column for it). Expand-only. Down: drop the column.
- **Tests:** `tests/unit/evidence/test_words.py` (coordinates, rotation, scanned and encrypted pages, control characters, caps, the isolated child); `tests/workflows/test_upload_processing_replay.py` (v4 committed, v1 to v4 replay, words after previews); `tests/workflows/test_trust_layer_backfill_replay.py`; `tests/integration/trust_kit/test_word_layer.py` (rows, sealed layer, idempotent, evidence bytes and fingerprint unchanged, backfill pending list).
- **Decision:** DEC-217 (coordinate space, page cap, what a page without text records).
- **Rollback:** revert the commit. Histories recorded with `patched("words")` replay only against code that has the patch, so once v4 runs in production the patch stays (ADR-090); remove it later with `deprecate_patch`. `evidence_pages` rows and layer objects are derived and harmless if left.

## Progress log
- 2026-10-24: plan written.
- 2026-10-24: built. Found 0109's `evidence_pages` can't be read back (storage checks size; no size column): migration 0119 adds `text_layer_size`. Histories `upload-processing-v4-words.json` and `trust-layer-backfill-v1-done.json` recorded; v1 to v4 replay. Tests live in `tests/integration/trust_kit/` (own conftest; parent-relative imports are banned, so a small superuser seeder is local). 13 unit, 9 integration, 14 replay tests pass; schema_check, trust kit schema and migrations-env integration files pass (199). Backend gates of `make check-fast` pass; its frontend `tsc` step fails in generated `packages/api-client/src/core/*.gen.ts`, which this branch does not touch.
- 2026-10-24 (with TASK-1005): found `insert_extraction` and `insert_preview` still name 0109's dropped one-per-source index in `ON CONFLICT`, so every extraction and preview insert failed after 0109 (no test ran them). Fixed in the T06 commit (`derivation_id` added to the conflict target) with a regression test in `trust_kit/test_word_layer.py`.
- 2026-10-24 (security review): a hostile MediaBox (zero, tiny, negative, NaN or over 14,400 pt) overflowed `numeric(8, 2)` and failed the step, the run and the backfill forever. Such a page is now unreadable with clamped geometry and no words; the v4 step no longer fails `upload_processing` when it fails for good, and the backfill counts and passes a failing source (`BackfillInput.failed`). New histories `upload-processing-v4-words-failed.json` and `trust-layer-backfill-v1-skipped.json`. Tests written first and seen failing (6 unit, 1 integration, 3 replay).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-217 | The contract's "unrotated page space" and the server-rendered PNG must share one space; the page cap and textless pages were not specified | No (ADR-166, ADR-110) |
