---
id: TASK-324
title: "Statement intake phases 2-3: transactions from PDF text, CSV and OFX, reconciled by code, approved by a person"
spec: SPEC-312
acceptance_criteria: [AC-5, AC-6, AC-7, AC-8]
risk_zone: red
status: done
branch: task-324-statement-transactions
worktree: spec005
created: 2026-10-21
updated: 2026-10-21
---

## Plan
- **Migration 0075:** `statement_datasets` and `statement_transactions`, both insert-only. CHECKs: the approver is human; opening + included total = closing; an excluded line has a reason. Rollback is the downgrade.
- **Evidence:**
  - `statements.py` (pure parsers and `reconcile`);
  - `statement_review.py` (`read_statement` runs in the child; `apply`, `statement_for`, `approve_statement`);
  - `statement_repository.py`;
  - models, registry, routes.
- **Matrix:** `statement.approve`. Reading follows `evidence.read`.
- **Synthetic data:** `card_statement_pdf` in `abacus_tools/synthetic/documents.py`.
- **Web:** `StatementReview.tsx` on `ItemDetail.tsx`.

## Definition of done
- [x] `tests/unit/evidence` (174, including `test_statements.py`) and the pinned gate tests pass.
- [x] A local DB smoke test passes: an unreconciled dataset and an agent approver are refused by CHECK, and a reconciled dataset with its lines is written and read back.
- [x] spec312statement, spec029checks and the ItemDetail tests pass.
- [x] check-fast passes.
