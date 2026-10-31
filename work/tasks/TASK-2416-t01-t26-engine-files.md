---
id: TASK-2416
title: T-01-T26 Engine diagnostics, PDF and acknowledgement adapters
spec: SPEC-000  # the backlog row; T-01 §3.10 and the tax-engine-bridge contract
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: red
status: in-review
epic: T-01
plan_key: T-01-T26
branch: s19-t01-t26
worktree: /Users/ayushkbhatia/Accrued/abacus-s19
created: 2026-10-30
updated: 2026-10-30
---

## Objective
Diagnostics into engine_diagnostics and issues (kind engine_diagnostic, dedupe on code plus field
through P-04 source_ref, error sets Export failed); engine PDFs classified by form into evidence;
the e-file status report parsed into pending ack rows; golden files.

Acceptance: "The IP PIN diagnostic raises one Action required issue however often the file is
re-imported, and the Ridgeline K-1 PDFs reach T-02's package as engine evidence."

## Plan (red)
Migration 0562 (on 0561): engine_acks. `tax/engine_files.py`, adapter parsers, evidence
`file_engine_copy`, review `record_engine_issue` export. Security: files parsed in the isolated
child, scanned before storage, last four only, engine text never in titles or logs.

## Progress log
- `2026-10-30` — Built on `s19-t01-t26` (stacked on `s19-t01-t27`, #893). Adapter unit tests pass
  (6/6); integration at the end review. DEC-1464.
