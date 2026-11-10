---
id: TASK-6615
title: "T-04-T16: Worksheets service: worksheet tree, fields with provenance, the human-edit applier with deterministic recompute of derived lines"
spec: SPEC-649
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
branch: s34-t04-t16
worktree: /Users/ayushkbhatia/Accrued/abacus-s34
created: 2026-11-10
updated: 2026-11-10
plan_key: T-04-T16
---

## Objective
Editing line 20 with a reason recomputes lines 33, 37 and the balance due in code, creates one
checkpoint and stales the Payments and credits sign-off, while an edit without a reason answers
422 reason_required.

## Plan (amber)
1. `tax/worksheet_formulas.py` (new): Form 1040 derived lines as code formulas keyed by
   `formula_ref` (21, 22, 24, 33, 34, 37), fixed-point recompute in `Decimal`, unknown refs fail
   closed.
2. `tax/worksheets.py` (new): the tree (group, sub-head, TSJ, new, edited), the fields with view
   state, citation counts, engine labels, `q` search; `recompute_after_edit` records each moved
   formula field as a `formula` version with cause `recompute` in the edit's unit of work.
3. T-04-T15's applier calls the recompute and rehashes every section.
4. Routes: `GET /v1/returns/{id}/worksheets` and `GET /v1/worksheets/{id}/fields` live.
5. Tests: `tests/unit/tax/test_t04t16_worksheets.py`.

## Progress log
- `2026-11-10` — Built; ruff, pyright clean; the app imports. Tests not run (end pass). Partial:
  the edit goes through P-04's generic field route, whose required citation note is the reason
  (its refusal is P-04's `invalid` with `field: citation_note`, not a tax-specific
  `reason_required` code) and whose `seen_seq` is the expected version (409); the provenance line
  text ("0 → 1,550 · Samuel · K-1 box 18A") is composed by the SPA from the version facts.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-3209 | Formulas are code by ref; the edit uses P-04's route; recompute in the edit's unit | no |
