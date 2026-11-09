---
id: TASK-6308
title: P-11-T35 tax form maps part 2, Schedule K-1 (1065, 1120-S, 1041), 1095-A, 1095-C, SSA-1099
spec: SPEC-000  # row (P-11-T35); P-11 F8, AC8.4, AC8.7
acceptance_criteria: [AC-1]
risk_zone: red
status: done
epic: P-11
plan_key: P-11-T35
branch: s32-p11-t35
worktree: /Users/ayushkbhatia/Accrued/abacus-s32
created: 2026-11-09
updated: 2026-11-09
---

## Objective
Box maps for the K-1s with their code lines, state attachments flagged for review and never
summed, 1095-A, 1095-C and SSA-1099, for TY2025 to TY2027.

## Plan (red)
- `evidence/form_extraction.py` (additive): `CodeBox` and `FormMap.code_boxes`
  (`extract_code_box`: "18A …" or "18 A …", the line's last money token, never summed);
  `FormMap.state_anchor` (pages with it are left unread and one `<form>.state_attachment` flag,
  `low_confidence`, is written); `FieldMap.box` (the box number before the anchor, so a caption
  inside a code line is never taken).
- Maps `evidence/forms/{k1_1065,k1_1120s,k1_1041,f1095a,f1095c}/{2025,2026,2027}.yaml` (TY2026
  inherits) and `ssa_1099/{2025,2026,2027}.yaml` (captions print the year, so no inheritance).
- Tests: `tests/unit/evidence/test_p11t35_tax_form_maps_part2.py`.
- No notice or part-1 map changes; dark behind the `tax_forms` variant like part 1.

## Progress log
- `2026-11-09` — Built; ruff, pyright clean; tests written, not run (end pass). The corpus's
  existing `ridgeline_k1` page now identifies as `k1_1065` (its 18A and 19A read as code lines).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-3008 | Code lines as fields, state attachments flagged and unread, box-number guard | no |
- `2026-11-09` — S32 end pass: gates, unit, contract, S32 integration and web suites run; fixes folded into the end-pass PR. Status done.
