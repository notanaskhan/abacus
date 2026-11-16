---
id: TASK-8341
title: "A-08-T14: Fieldwork-test routes: adopt (L1), the deviation log, SHL-15's prefill and the workbook"
spec: SPEC-657
acceptance_criteria: [AC-1, AC-2]
risk_zone: amber
status: in-review
branch: a08-t14-fieldwork-routes
worktree: /Users/ayushkbhatia/Accrued/abacus-s47g04
created: 2026-11-16
updated: 2026-11-16
plan_key: A-08-T14
---

## Objective
Spec section: SPEC-657 F2, F3 (AC-1.7 to AC-1.9, AC-2.1, AC-2.2). Fieldwork-test routes: adopt (L1), the deviation log, SHL-15's prefill and the workbook.

## Plan (amber)
1. `POST /v1/tests/{id}/adopt`: L1 through `review.api.record_sign_off` on the grid's current content hash (409 `content_changed`); `record_sign_off` now returns the new sign-off's id (additive).
2. `POST /v1/tests/{id}/deviations`: by the row's position on AUD-12; the UDL in code as a fraction against the sample set version's recorded tolerable rate.
3. `POST /v1/tests/{id}/items/{item}/exception`: the grid's exception prefill.
4. `GET /v1/tests/{id}/export.xlsx`: the kernel's deterministic workbook, every digit of a record key but the last four masked; audited (`attribute_test.exported`).

## Progress log
- `2026-11-16` — Built in the S47 sequential stack (DEC-5326). Lint, pyright clean; the app imports; client regenerated. Partial: the JE item detail's C4 citation reads stay the grid's existing citations. Gates and
  tests run once at the S47 end pass (build first, test last).
