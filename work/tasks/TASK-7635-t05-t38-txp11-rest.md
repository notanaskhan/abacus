---
id: TASK-7635
title: T-05-T38 rest — TXP-11 overlays (a2, a3, d) and the version picker
plan_key: T-05-T38
spec: SPEC-651
acceptance_criteria: [AC-F4]
risk_zone: green
status: in-review
branch: t05-t38-txp11-rest
worktree: /Users/ayushkbhatia/Accrued/abacus-s40
created: 2026-11-13
updated: 2026-11-13
---

## Objective
Finish TXP-11, partial in TASK-7628: the selected cell's provenance (SHL-09, a3) and citations
(SHL-07, a2) with the source viewer (SHL-08, d), and a working version picker.

## Plan
- `agents/engagement_run.py`: `WorkItemRun.finished_at` (read only).
- `tax/workbook_contract.py`: `WorkbookVersionOut`, `WorkbookOut.versions`; the sheet route reads
  `?version=` (an earlier finished run, via `values_as_of`; 404 for an unknown one) and fills the
  live cells' `author` and `citation_ids` (DEC-4630).
- Web: `screens/TXP-11/{index,Workpaper,Overlays,copy,TXP11.test}`; fixtures: workbook versions,
  citations on D12 and J16, `GET /v1/citations/{id}`.
- Rollback: revert; the picker returns to a label.

## Partial
- Open in Excel stays T-05-T60. The server's sheet titles differ from the handoff's.

## Progress log
- `2026-11-13` — Built (DEC-4630).
