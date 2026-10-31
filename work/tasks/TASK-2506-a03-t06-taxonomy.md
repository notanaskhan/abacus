---
id: TASK-2506
title: A-03-T06 taxonomy service (workbook import, dated human-only publish, one draft, catalogue and picker)
spec: SPEC-580
acceptance_criteria: [AC-17]
risk_zone: red
status: in-review
epic: A-03
plan_key: A-03-T06
branch: s20-a03-t06
created: 2026-10-30
updated: 2026-10-30
---

## Objective
What A-03-T06 still needs after SPEC-316's mapping slice (0079) and ADR-341: the workbook import
with problems by sheet, row and code, a dated publish only a person can make, one live draft per
set, the catalogue and picker with Recently used, and `ledger.api.grouping_catalogue`.

## Verify first (status: partial)
Built (TASK-345, 0079): grouping_sets, versions frozen on publish, groupings, fs_lines,
fs_line_range_rules, mapping_sets, mapping_set_edits; CSV import with problems; publish with fresh
MFA and `published_actor_kind = 'human'`. Missing: XLSX, overlap row, effective date, one draft,
a person's session at the DB, catalogue/picker reads. The plan's stored `account_mappings` and
`account_mapping_events` are replaced by ADR-341 §5 and are not built.

## Plan (red)
- Migration `0521_grouping_set_publish.py` (revises 0520): `effective_from` (+ NOT VALID CHECK on
  publish), status `discarded`, guard trigger (discarded frozen; publish only with
  `app.actor_kind = 'human'`), grant on `effective_from`. Registry and model updated.
- `ledger/mapping.py`: `Problem.sheet`; overlap reported on the later range's row
  (`finish_grouping_set`); `import_parsed_grouping_set` discards the set's earlier draft;
  `publish_version(..., effective_from)` refusing a non-draft (`grouping_set_not_draft`);
  `grouping_catalogue`, `grouping_version_id`, `recently_used` (the person's own edits).
- `ledger/taxonomy_workbook.py`: `parse_grouping_workbook` (Groupings, FS lines, Number ranges;
  values only, formula-looking cells kept as text, 2 MB cap).
- `assurance/mapping.py`: `import_file` (XLSX or CSV raw body), `publish(..., effective_from)`
  (business date when absent), `catalogue`, `picker`. Routes: `POST /v1/grouping-sets/imports/file`
  (raw body, 413 over 2 MB), publish body `{effective_from?}`, C9 v2 catalogue and picker live.
- Rollback: downgrade 0521; the v0 routes keep working without the new body.

## Acceptance
| Check | Test |
|---|---|
| Clean workbook, zero problems | `tests/unit/ledger/test_a03t06_taxonomy.py::test_ac17_a_clean_workbook_imports_with_zero_problems` |
| Overlap row problem (workbook and CSV) | `test_ac17_an_overlapping_range_returns_its_row_problem`, `test_ac17_the_csv_path_*`; `test_mapping.py` now pins row 6 |
| Unknown refs, classes, duplicates, sheets | `test_ac17_unknown_*`, `test_ac17_a_missing_sheet_*` |
| Ledger dependency-free | `test_ac17_ledger_keeps_an_empty_dependency_set_and_imports_no_module` |
| Publish only by a person, dated; one draft; discarded frozen | `tests/integration/backfill/test_a03t06_taxonomy_db.py` |
| Catalogue and picker live | `tests/contracts/c09_ledger/test_c09_v2_stub.py` (LIVE) |

## Progress log
- 2026-10-30: built (tests first, run at the end review). DEC-1556. Changed one existing assertion
  (`test_mapping.py`: overlap row 0 → 6) because SPEC-580 AC-17 now requires the row; stricter.
