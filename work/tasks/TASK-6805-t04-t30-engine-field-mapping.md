---
id: TASK-6805
title: "T-04-T30: Engine field mapping as new files (tax/export_fields.py and an integrations engine profile): engine_field_key payload of return fields into the W2 file-bridge workbook from an approved checkpoint only; engine-computed lines imported as engine_import versions inside a pending import checkpoint; tie-out differences as engine_diagnostic issues; Out of sync after edits"
spec: SPEC-649
acceptance_criteria: [AC-10]
risk_zone: red
status: in-review
branch: s36-t04-t30
worktree: /Users/ayushkbhatia/Accrued/abacus-s36
created: 2026-11-11
updated: 2026-11-11
plan_key: T-04-T30
---

## Objective
An export uses only fields from the current approved checkpoint, an import changes no value until a
person approves its checkpoint, a 23,014 vs 23,015 difference raises one engine_diagnostic issue,
and the never-transmit tests stay green.

## Plan (red: written before the build)
1. `review.api`: `values_as_of` (each target's values recorded at or before a time),
   `checkpoint_recorded_at`, `changed_since_any` (additive reads).
2. `integrations/engine_profile.py`: the CCH Axcess field profile (columns, validated key shape).
3. `tax/export_fields.py`: `export_values` (the approved checkpoint's values; worksheet fields
   under their engine keys; engine lines left out; an unmapped key is 409
   `engine_field_unmapped`), `mirror_engine_lines` (approved import → `engine_import` versions on
   worksheet engine fields in the same checkpoint), `raise_tie_outs` (one `engine_diagnostic`
   issue per `tieout:<key>`), `worksheets_changed_since` (Out of sync).
4. Wire: `export.py` exports `export_values` (was the latest values: a gap against AC-10.1);
   `engine_import.py` raises tie-outs after an upload, mirrors lines on approval, and the sync
   chip reads worksheet edits.
5. Tests: `tests/unit/tax/test_t04t30_export_fields.py`.
6. Rollback: revert; the export reads the latest values again.

## Progress log
- `2026-11-11` — Built (S36). Unit tests written, not run (end pass).

## Partials
- The over-HTTP export-and-import AC suite on the Feld return needs T-04-T28's worksheets in the
  seed; it is written with T-04-T28's slice (end pass).
- A values file that matches Accrued's return fields exactly (no diff) is taken at once and skips
  the tie-out pass (its early return sits inside the import's unit of work).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-3405 | Export as of the approved checkpoint, profile, import mirror, tie-out | no |
