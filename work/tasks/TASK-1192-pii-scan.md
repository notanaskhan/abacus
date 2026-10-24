---
id: TASK-1192
title: PII detection by code, upload_processing v5 pii_scan, synthetic PII corpus (P-03-T13)
spec: SPEC-322
acceptance_criteria: [AC-23, AC-30]
risk_zone: red
status: in-progress
epic: P-03
plan_key: P-03-T13
branch: s8a-evidence-pipeline
created: 2026-10-25
updated: 2026-10-25
---

## Objective
"The seeded corpus (W-2 box a 000-00-6081, K-1 EIN, 1099 recipient TIN) is detected at recall 1.0, and pages without a text layer are recorded not_scannable, never silently clean."

## Plan (red zone)
- **Detector** `evidence/pii.py` (code, never a model; P-03 §4.4): words grouped into lines; label families (TIN, EIN, account, routing, date of birth) anchor a candidate right of them on the same line or on the line just below; label-anchored values are masked whatever their validity; unlabelled ones only when valid (`kernel.tin_patterns` for SSN, ITIN and EIN; the ABA checksum for nine bare digits). Pure `detect(page_no, words)`.
- **Activity** `upload.pii_scan` → `pii_scan_upload`: reads the word layer (`pages_of`, which already hides withdrawn versions), writes one `pii_scan_runs` row (scanned and not-scannable pages) and its `pii_regions` (value sealed with the tenant key, bound to the region id) in one system unit of work, audited `upload.pii_scanned`. Idempotent on (source, `DETECTOR_VERSION`). Skips a withdrawn version (DEC-298) and an active-content PDF (DEC-296: its extraction says `active_content`), and writes no run for a source with no word layer (fail closed: nothing reads as scanned).
- **Workflow** `UploadProcessing` v5 `workflow.patched("pii_scan")` after `words`, never failing the run; histories `upload-processing-v5-pii-scan.json` and `-v5-pii-scan-failed.json` recorded with `abacus_tools.workflows.record_upload_processing`; v1 to v4 replay unchanged.
- **Corpus** `abacus_tools/synthetic/documents.py` `pii_corpus()` (W-2, K-1, 1099-INT, direct deposit; synthetic ranges only).
- **Tests:** `tests/unit/evidence/test_pii_detector.py`, `tests/integration/trust_kit/test_pii_scan.py`, `tests/workflows/test_upload_processing_replay.py`. Rollback: revert; the patch marker keeps new histories replaying only with the step, so a revert must keep `patched("pii_scan")` as a no-op branch (ADR-090).

## Progress log
- 2026-10-25: built as planned. 12 unit, 5 integration and 16 replay tests pass. **Deferred:** the trust-layer backfill also scanning old uploads (it runs only `upload.words`; a patched backfill step belongs with P-03-T15's masked-preview backfill); masked renditions (T15); reveal (T16); P-03-T21's independent suite. Inbox files are scanned too (the step runs for both kinds).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-322 | The detector's geometry, kinds and skips are not fixed by §4.4 | No |
