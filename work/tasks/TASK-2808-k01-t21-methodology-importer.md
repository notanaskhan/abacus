---
id: TASK-2808
title: K-01-T21 methodology.importer capability and MethodologyImportWorkflow
spec: SPEC-000  # K-01-T21 row; K-01 §4.4, §6; docs/contracts/methodology-programs.md
acceptance_criteria: [AC-1]
risk_zone: red
status: in-review
epic: K-01
plan_key: K-01-T21
branch: s23-k01-t21 (stacked on s23-k01-t20)
worktree: /Users/ayushkbhatia/Accrued/abacus-s23
created: 2026-11-01
updated: 2026-11-01
---

## Objective
- **[AC-1]** "On the fake model the seeded upload ends Needs review with 67 steps, 3 flags and
  every displayed citation verified, and an uncleared non-synthetic firm gets 409
  importer_not_enabled."

## Plan (red)
- Agents: spec YAML + `_specs.py`, prompt `methodology.import_parse@v1`, `ImportBatchOutput`
  (extra forbidden), `methodology_import.py` (admission, start, activities' bodies, fake parse),
  `methodology_import_workflow.py`, activities and the background work class.
- Methodology: `document_import.py` (slot, source read, pages store, progress, finish/fail),
  `start_import` uses the slot; `ProgramStep.parse_confidence` mapped (0224's column).
- No migration (0224/0580 hold every column), no matrix edit (`methodology.parse` exists), no flag
  (`methodology.importer` exists).
- Synthetic: `ebp_v3_document_pdf()` (67 steps, 3 flagged).
- Tests: `tests/unit/agents/test_k01t21_methodology_importer.py` (the pure path end to end: 67
  steps, 3 flags, all verified; refusals; admission). Still to write at the end review: an
  integration test of `finish_document_import` and the route's 409, and the workflow's replay
  history (needs a Temporal run).
- Rollback: revert; with the slot unregistered the document path is 409 as before.

## Progress log
- `2026-11-01` — built; ruff and pyright clean; `make regenerate` run. Tests at the S23 end
  review; security review of this red diff there.

## Decisions made during this task
DEC-1856.
