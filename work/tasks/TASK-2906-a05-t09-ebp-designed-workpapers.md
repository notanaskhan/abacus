---
id: TASK-2906
title: A-05-T09 register the nine EBP designed workpapers
spec: SPEC-641
acceptance_criteria: [SPEC-641 §5]
risk_zone: amber
status: in-review
epic: A-05
plan_key: A-05-T09
branch: s24-a05-t09
worktree: /Users/ayushkbhatia/Accrued/abacus-s24
created: 2026-11-01
updated: 2026-11-01
---

## Objective

EBP-01 to EBP-09 as designed workpapers: rail rows, program-step references, deterministic cell-address maps and Open-in-Excel layouts, the export section.

## Acceptance (backlog)

Rail rows appear on the Northwind cockpit with canonical statuses, and every seeded anchor resolves to exactly one cell in the XLSX export.

## Plan

- **Migration `0641_workpapers_ebp_kinds`** (expand-only, on 0640): `workpapers.kind` admits the nine EBP kinds; `WORKPAPER_KINDS` and the contract's `WorkpaperKind` follow.
- **workpapers**: `layouts.py` (address parse and resolve, `register_designed_layout`), the export writes a designed paper positionally, `designed.py` (`work_item_papers`), `repository.papers_of_work_item`.
- **assurance** `ebp_designed.py`: the nine papers (code, kind, title, band, order, program refs, sheets, anchors), a rail row each (`link: planned` until each screen ships), layouts, `ebp_workpapers` export section; registered from `assurance.api`.
- Already provided and reused: the `workpaper` reviewable and `workpaper_cell` citable (A-04-T04).
- C15: workpapers carry no search projection yet (the index lands at S39); no slot registration needed for v1 (DEC-1954).
- SPEC-641 (the cell-address scheme). Tests: `tests/unit/workpapers/test_a05t09_designed_layouts.py`, `tests/integration/backfill/test_a05t09_ebp_rail.py`.

## Progress log

- 2026-11-01: built in abacus-s24. A smoke import listed the nine rail rows; tests written, not run.
