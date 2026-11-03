---
id: TASK-3208
title: A-05-T28 ADR P-58 ledger path (document-extracted trial balances)
spec: SPEC-640
acceptance_criteria: [AC-24]
risk_zone: red
status: in-review
epic: A-05
plan_key: A-05-T28
branch: s26-a05-t28 (stacked on s26-a05-t26)
worktree: /Users/ayushkbhatia/Accrued/abacus-s26
created: 2026-11-03
updated: 2026-11-03
---

## Objective
"A trust-report TB with one unverified line or a footing difference is refused, and an adopted
snapshot shows its 'document extraction' provenance on AUD-06."

## Plan (red)
- Migration 0659 on 0658: `ledger_snapshots.source_evidence_version_id` and
  `extraction_run_id`, insert-only grants, and a CHECK that `document_extraction` carries both.
- `ledger.api.record_document_snapshot(tx, …, line_citations, supported)`:
  - code foots the lines (debits = credits and the declared totals; 422 `document_unbalanced`);
  - every line's citation must be one the caller's C4 check (`evidence.api.supported_citations`)
    returns (422 `line_unverified`, fact `account_code`);
  - stored lines keep `citation:<id>` as their source reference.
  - It is never adopted here; A-02's human-only TB-of-record version adopts it.
- `docs/architecture/error-codes.yaml` regenerated, now carrying every S26 code so far.
- Tests:
  - `tests/unit/ledger/test_a05t28_document_snapshot.py`;
  - `tests/integration/test_a05t28_ledger_document_migration.py`.
- Rollback: `alembic downgrade 0658`.

## Progress log
- 2026-11-03: built. AUD-06's provenance line reads `source_kind`/`source_evidence_version_id`
  once EBP-06's caller (A-05-T35) records trust-report TBs; that display is the FE row's. Tests at
  the S26 end review.

## Decisions made during this task
DEC-2208.
