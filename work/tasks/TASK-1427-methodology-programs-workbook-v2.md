---
id: TASK-1427
title: Workbook v2 and migration methodology_programs (K-01-T05)
spec: SPEC-008
acceptance_criteria: [AC-1, AC-2]
risk_zone: amber
status: in-review
epic: K-01
plan_key: K-01-T05
branch: s11-home
created: 2026-10-27
updated: 2026-10-27
---

## Objective
A firm's programs and steps come in through the workbook import, never through code. Acceptance:
the BH EBP v3 workbook imports 7 programs, 67 steps and 24 requests, a legacy three-sheet
workbook still imports, and the database refuses any update to a published version's steps.

## Plan
- Migration `0224_methodology_programs` (after 0223): `programs`, `program_steps`,
  `program_step_pbc_links` (insert-only), forced RLS, column grants (draft step content only;
  never `mandatory`/`lock_note`), `methodology_content_frozen()` (SECURITY INVOKER, pinned
  search path) on all three.
- `workbook.py`: optional Programs and Steps (behind `methodology.programs`), Account rules
  optional, ADR-052 problem codes, row limits, by-header columns.
- `repository.py`: programs, steps with `assign_step_keys` (step_id, else the previous
  version's key by program and number, else derived), links; `_land_for_review` under
  `methodology.lifecycle`; `family` on a new template.
- `workbook_template.py` + `GET /v1/methodology/workbook-template.xlsx` (deterministic, headers
  only, no firm content).
- Catalog: programs feed search keywords and `flags_open`.
- Registry, schema check test, LIST_EXEMPT (`_prior_keys`), route introspection.
- Tests: `tests/unit/methodology/test_k01t05_workbook_v2.py`,
  `tests/integration/backfill/test_k01t05_methodology_programs.py`; the catalog test covers the
  needs-review landing.
- Contract `docs/contracts/methodology-programs.md`; `make regenerate` (isolation test list),
  `make generate`. DEC-572.
- Rollback: downgrade 0224 (drops the three tables and the function) and revert; the flags stay
  off.

## Progress log
- 2026-10-27: built.
