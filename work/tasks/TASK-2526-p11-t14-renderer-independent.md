---
id: TASK-2526
title: P-11-T14 Independent AC tests (ADR-078) for the renderer
spec: SPEC-520  # AC-6 to AC-9, AC-15, AC-16, AC-20, AC-26, AC-27
acceptance_criteria: [AC-6, AC-7, AC-8, AC-9, AC-15, AC-16, AC-20, AC-26, AC-27]
risk_zone: amber
status: in-review
epic: P-11
plan_key: P-11-T14
branch: s20c-p11-t14
worktree: /Users/ayushkbhatia/Accrued/abacus-s20b
created: 2026-10-31
updated: 2026-10-31
---

## Objective
Independent AC tests for the renderer: deny-all fetcher including a metadata-address URL,
hostile variable escaping, byte stability across two containers, watermark and final-render
rules, agent draft-only (INV-1), insert-only versions, walls and client refusal (INV-3, INV-4),
audit attribution (INV-5).

Acceptance (backlog row): "Every rule is proven by tests written outside the implementing
session and all pass against the merged renderer."

## Plan
- `tests/golden_render/test_p11t14_renderer_independent.py` (image-bound, `make golden-render`
  after the two-container check): AC-9 metadata URL as an asset and in a value, AC-8, AC-6/AC-20
  PDF and DOCX bytes, AC-7.
- `tests/integration/test_p11t14_renderer_independent.py`: INV-1 at the service and the database
  CHECK, the final-render rule, insert-only triggers on all five tables, INV-5 attribution,
  INV-3/INV-4.
- Written from SPEC-520 and C11 v1; fixtures reused from P-11-T08/T11's probe kind.

## Progress log
- `2026-10-31` — Built on `s20c-p11-t14` off main. Integration half 5 passed; the image-bound
  half runs at the end-of-batch `make golden-render`.
