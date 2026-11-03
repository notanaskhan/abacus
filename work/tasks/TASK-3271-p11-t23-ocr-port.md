---
id: TASK-3271
title: P-11-T23 OCR port kernel/ocr.py (TextractOcr, FakeOcr) and the evidence gate
spec: SPEC-000  # row; P-11 §4.4 AC7.2
acceptance_criteria: [AC-1]
risk_zone: red
status: in-review
epic: P-11
plan_key: P-11-T23
branch: s27-p11-t23
worktree: /Users/ayushkbhatia/Accrued/abacus-s27
created: 2026-11-04
updated: 2026-11-04
---

## Objective
"Each refusal names its first failing condition and is audited without document text, FakeOcr
replays byte-identical layers, and no TIN or page text reaches logs, metrics or error tracking."

## Plan (red)
- `kernel/ocr.py`: `OcrProvider`; `TextractOcr` (one synchronous call per page's bytes, backoff
  on throttling, a per-process cache keyed by image SHA-256 and API); `FakeOcr` (recorded JSON);
  `normalise` to page points with word confidence; logs carry counts and hashes only.
- `evidence/ocr_gate.py`: `first_refusal` in AC7.2's order (kill switch = the platform's
  `model_route_block` on route `textract`, firm flag `evidence.ocr`, provider terms, boundary
  basis, §7216 consent or counsel's `tri_basis`) and `record_run` (one `ocr_runs` row and an
  audit event, identifiers and counts only).
- import-linter: only `abacus.modules.evidence` imports `abacus.kernel.ocr`.
- Tests: `tests/unit/evidence/test_p11t23_ocr_port.py`.
- Not here: the OCR workflow step over evidence pages and the C4 v1.1 routes going live (P-11-T25
  onward); per-tenant daily page caps.

## Progress log
- 2026-11-04: built; `lint-imports` 7 kept, 0 broken.

## Decisions made during this task
DEC-2251.
