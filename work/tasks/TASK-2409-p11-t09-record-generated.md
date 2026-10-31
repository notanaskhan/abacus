---
id: TASK-2409
title: P-11-T09 evidence.api.record_generated (rendered bytes as an immutable evidence version)
spec: SPEC-000  # the backlog row; P-11 §4.2 and C11 v1
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: red
status: in-review
epic: P-11
plan_key: P-11-T09
branch: s19-p11-t09
worktree: /Users/ayushkbhatia/Accrued/abacus-s19
created: 2026-10-30
updated: 2026-10-30
---

## Objective
Rendered bytes stored as an immutable evidence version (channel generated, provenance, Object
Lock) in the caller's unit of work, then the words, PII scan and masked preview steps as for
uploads.

Acceptance: "A rendered PDF's evidence fingerprint equals its render_hash, its pages open masked in
SHL-08, and no code path rewrites its bytes."

## Plan (red)
Files: `evidence/generated_copies.py` (new), `evidence/api.py` (exports), `reporting/documents.py`
(`record_file`), `tests/integration/test_p11t09_record_generated.py`, DEC-1457. Stacked on #883
(P-11-T08). No migration (channel `generated` exists since 0270; method `uploaded` per precedent).
Security: tenant-key check on the stored object, fingerprint = render hash, insert-only rows,
storage before the transaction. Rollback: revert; no caller yet.

## Progress log
- `2026-10-30` — Built on `s19-p11-t09` (stacked on `s19-p11-t08`; tests at the end review).
