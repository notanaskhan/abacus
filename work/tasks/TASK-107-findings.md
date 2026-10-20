---
id: TASK-107
title: "SPEC-043: findings register, misstatements, and the summary of uncorrected misstatements against materiality; a Findings tab and Raise finding from exceptions"
spec: SPEC-043
acceptance_criteria: [AC-1, AC-2, AC-3, AC-4, AC-5]
risk_zone: red
status: done
branch: spec-043-findings
worktree: spec005
created: 2026-10-20
updated: 2026-10-20
---

## Plan
Migration 0064; `fieldwork/findings.py`; routes `GET`/`POST /findings`, `POST /findings/{id}/misstatement`, `GET /findings/summary`; matrix actions; a Findings tab plus Raise finding on exception rows. Approved by founder (2026-10-20, "proceed").

## Done
- Migration 0064 (`findings`, `misstatements`; insert-only).
- `fieldwork/findings.py`: `raise_finding`, `record_misstatement`, `findings_for`, `summary_for`, and `summarise`. The summary is pure code: uncorrected misstatements above clearly trivial (by absolute amount), by kind; the absolute total against performance and overall materiality.
- Routes `GET`/`POST /findings`, `POST /findings/{id}/misstatement`, `GET /findings/summary`; matrix `finding.raise` and `misstatement.set`.
- Web:
  - A Findings tab with the summary card (by kind, total, position against materiality) and the register (DataTable).
  - "New finding" (Sheet), and a finding drawer to record the misstatement (kind, signed amount, account from the ledger, corrected).
  - "Raise finding" on fieldwork exception rows.

## Definition of done
- [x] `test_findings.py` (3), `spec043findings.test.tsx` (2); the fieldwork screen tests pass; `make check-fast` passes.
- [ ] Not walked live; owed: ADR-078 integration tests.
