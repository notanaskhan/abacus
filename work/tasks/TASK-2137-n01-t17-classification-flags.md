---
id: TASK-2137
title: N-01-T17 Classification and code flags on intake attachments
spec: SPEC-000  # N-01-T17 row; N-01 §3.4 and §4.2 are the spec
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: red
status: in-review
epic: N-01
plan_key: N-01-T17
branch: s16-n01-t17
created: 2026-10-30
updated: 2026-10-30
---

## Objective
Code classifies and flags every intake attachment before any agent proposes (INB-02 a, b, c, g;
DF-04). Acceptance (backlog row): "The 2024 1095-C is flagged wrong year and duplicate, and the
Collins W-2c forces Hold with 7713 vs 7731."

## Plan
- Migration `0404_document_classifications` (evidence): N-01 §4.2's columns, forced RLS,
  insert-only (the trust kit's `trust_kit_immutable`), insert-column grants; registry and
  schema_check pins.
- `evidence/classifier_rules.yaml` (repo parameter file, `version: c1`) and the pure
  `evidence/classifier.py`: form family, code, kind and tax year from the file name and the first
  two pages' text layer; per-field confidences; the corrected cue; never reads a form number as a
  year.
- `evidence/classification.py`: `classify_intake` (word layer + PII last fours in, one
  classification row and a `document.classified` event out), `filed_classification_match`
  (possible replacement), `version_with_fingerprint` (duplicate of a filed version), all
  client-scoped and id-only.
- `communications/triage_flags.py` (pure severities) and `triage_classify.py`
  (`communications.attachment_classified`): one new flag run per call, `classification_id` set on
  the attachment, `inbox_attachment.flagged` audited. AttachmentTriage runs it after the upload
  steps behind `workflow.patched("n01-t17-classify")` (ADR-090); old histories replay unchanged.
- Cross-module reads through api: `organisations.entity_tin_last4s` (masked last fours only) and
  `engagements.client_tax_years` (active work items' period-end years).
- Tests: `tests/unit/communications/test_n01t17_code_flags.py` (pure),
  `tests/integration/backfill/test_n01_t17_classification.py` (the acceptance, insert-only).
- Rollback: the workflow patch is skipped by removing the branch only after every run started
  with it has closed; the migration's downgrade drops the table.

## Decisions
- DEC-1177 (severities, wrong-year basis, the parameter file, candidates seam).

## Progress log
- 2026-10-30: built. Unit tests pass; integration tests run at the end review (build-first).
  `ambiguous_candidates` is a pure rule over destination scores; the matcher (N-01-T22, S17)
  supplies them, so it never fires until then.
