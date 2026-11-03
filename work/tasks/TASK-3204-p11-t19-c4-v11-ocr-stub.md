---
id: TASK-3204
title: P-11-T19 C4 v1.1 additive stub for OCR and box extraction
spec: SPEC-520
acceptance_criteria: [AC-34]
risk_zone: red
status: in-review
epic: P-11
plan_key: P-11-T19
branch: s26-p11-t19 (stacked on s26-t03-t04)
worktree: /Users/ayushkbhatia/Accrued/abacus-s26
created: 2026-11-03
updated: 2026-11-03
---

## Objective
"N-04 and T-04 can build NOT-01 b-d and TAX-03 a against seed fixtures, and the C4 v1 consumer
suite stays green."

## Plan (red)
- Matrix: `evidence.ocr_retry`, a person's act; agent, system and portal deny.
- Flags: `evidence.ocr` (boolean) and `evidence.form_extraction` (variant
  off/notices/notices_tax_forms/all).
- `evidence/ocr_contract.py`: `GET …/fields`, `GET …/tables`, `POST …/text/retry` as 501 stubs.
  `ViewerPageOut` gains optional `text_source` and `ocr`. `events.py` gains
  `evidence_text.ready`, `extracted_fields.recorded` and `ocr_run.refused` (identifiers only), and
  the refusal reasons.
- `make generate`; `c04-citations-viewer.md` §v1.1.
- Tests: `tests/contracts/p11/test_p11t19_ocr_stub.py`.
- Rollback: revert and regenerate.

## Progress log
- 2026-11-03: built. Tests at the S26 end review.

## Decisions made during this task
DEC-2204.
