---
id: TASK-2317
title: T-01-T19 engine import and diff (W2 file mode)
spec: SPEC-501
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: red
status: in-review
epic: T-01
plan_key: T-01-T19
branch: s18-t01-t19
worktree: /Users/ayushkbhatia/Accrued/abacus-s18
created: 2026-10-30
updated: 2026-10-30
---

## Objective
Engine files in: migration 0465 (links, sync events, import diffs, diagnostics); upload through
the scanner and the isolated parse; CCH values adapter as pure functions; diff by code into a P-04
import checkpoint; approve accepted rows into "Engine import Vn"; reject with a reason; the chip,
including out of sync from field values changed after the last sync.

## Plan
- `review`: `record_import_proposal`, `decide_import` (checkpoints), `current_values`,
  `changed_since` (field values), exported.
- `tax`: `engine_adapter.py` (pure), `engine_repository.py`, `engine_import.py` (red), five
  routes live in `engine_contract.py` (raw-body upload), registry and schema_check entries.
- `tax/approval.py`: reviewable facts hash as empty before the first checkpoint.
- Error catalogue, generated client, contract doc §2/§7, DEC-1363.
- Tests: `tests/unit/tax/test_t01t19_engine_adapter.py`, `tests/integration/
  test_t01t19_engine_import.py`; engine stub contract test lists the five routes live.
- Rollback: revert; 0465 downgrade drops the four tables.

## Progress log
- `2026-10-30` — built (DEC-1363). Unit (24 with T18's) and contract (43) tests run once;
  integration waits for the S18 end review. Stacked on T-01-T18 (#832). `[skip ci]`.

## Handoff
- **Current state:** built, PR open, held for the S18 batch.
- **Exact next step:** T-01-T20; T-01-T26 raises `engine_diagnostic` issues and imports PDFs.
