---
id: TASK-7834
title: "P-09-T11: the trace PDF through the real renderer"
spec: SPEC-000  # code partial (S0-S38 inventory, bucket C)
acceptance_criteria: [AC-1]  # the row's acceptance
risk_zone: green
status: done
branch: p09-t11-real-render
worktree: /Users/ayushkbhatia/Accrued/abacus-lo39-rec
created: 2026-11-14
updated: 2026-11-14
plan_key: P-09-T11
---

## Objective
P-09-T11's open clause: a real WeasyPrint render of a trace PDF.

## Delivered (#1946)
- `backend/tests/golden_render/test_p09t11_trace_pdf_render.py`, image-bound: through the
  composition root's registered renderer, two exports are byte-identical, the PDF carries the
  JSON's run and rows, a 620-row timeline continues across pages, an emoji prints as "?".

## Progress log
- 2026-11-14: written; ruff and pyright clean. `make golden-render` did not finish here (Docker
  stopped during the image build); CI's render goldens job runs it at the batch merge.
- 2026-11-14: merged; passed in main CI 43522183908 (0152ac5d6). Row done.
