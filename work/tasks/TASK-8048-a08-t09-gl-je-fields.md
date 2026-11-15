---
id: TASK-8048
title: "A-08-T09: GL JE fields (ADR P-58), expand-only migration 0888, column maps, journal_entries"
spec: SPEC-657
acceptance_criteria: [AC-0, AC-1]
risk_zone: red
status: in-review
branch: a08-t09-gl-je-fields
worktree: /Users/ayushkbhatia/Accrued/abacus-s45
created: 2026-11-15
updated: 2026-11-15
plan_key: A-08-T09
---

## Objective
The GL half of P-58: posting user, entry time, source and approver where exports carry them, an
availability fact per snapshot, and `ledger.api.journal_entries` grouped by reference.

## Plan (red: written before the build)
1. Migration **0888** `gl_je_fields` (expand-only; nullable columns; text[] default '{}').
2. **Protected** `connections/gl_formats.py` (optional JE headers) and `connections/gl_parse.py`
   (optional roles, normalised source and time, `je_fields_available`).
3. `ledger/general_ledger.py` (`GlEntry` fields with defaults, `GlSummary.je_fields_available`),
   `models.py`, `registry.py` insert columns, `gl_service.py` (`journal_entries`,
   `je_fields_available`), `api.py` exports.
4. Tests: parser with and without the columns, Hypothesis fuzz on the JE columns, expand-only check.
Rollback: downgrade 0888 drops the five columns; no data depends on them yet.

## Progress log
- `2026-11-15` — Planned at the S45 kickoff (#2010); plan above written before building.
- `2026-11-15` — Built (DEC-5033). ruff and pyright clean on ledger and connections. Tests
  written, run at the end pass (with migrations up/down/up).
- **Human:** `work/approvals/A-08-T09.yaml` by Ayush (non-author approval) and ADR-400 acceptance
  before the batch merge. The export column names are from each system's documentation and
  synthetic fixtures; check them against anonymised pilot exports when shared (A-08 R2).
