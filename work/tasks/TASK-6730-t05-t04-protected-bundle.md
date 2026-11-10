---
id: TASK-6730
title: "T-05-T04: S35 protected bundle: tax matrix rows, three flags, tax_entity_returns entitlement (requires review), protected paths and import-linter entries"
spec: SPEC-651
acceptance_criteria: [AC-0]
risk_zone: red
status: in-review
branch: s35-t05-t04
worktree: /Users/ayushkbhatia/Accrued/abacus-s35
created: 2026-11-10
updated: 2026-11-10
plan_key: T-05-T04
---

## Objective
The bundle merges first in S35, generated matrix tests show agent deny on every human verb, and make check-fast is green.

## Plan (red: written before the build)
- **Matrix** (`docs/architecture/permission-matrix/tax.yaml`):
  - 12 actions. Reads: `workbook.read`, `allocation_structure.read`, `tax_memo.read`, `tax_reconciliation.read`; the agent gets only its task scope.
  - Human verbs (`agent: deny`, system, platform support and portal principals deny): `workbook.edit`, `workbook.export` (review function, fresh MFA), `workbook_import.create`, `workbook_run.start`, `tax_ownership.edit`, `allocation_structure.edit`, `tax_memo.edit`, `tax_memo.draft`.
  - No independence row (T-05 §4.3).
  - Regenerated: `_matrix.py`, `actions.gen.ts`.
- **Flags** (`docs/architecture/feature-flags/tax.yaml`): `tax.entity_workspace`, `tax.workbook_run`, `tax.entity_agents`.
  - Boolean, default off, owner ayushkbhatia, created 2026-11-10, expiring 2027-05-07 under DEC-137 (T-04-T09's dates). The plan's Feb 24 to May 23, 2028 calendar maps onto the solo edition's.
  - `_flags.py` regenerated.
- **Entitlement:** `tax_entity_returns` joins `platform.entitlements` `Module` and `REVIEWED_MODULES` (requires review: refused for a non-synthetic firm until the CPA memos' check registers). Migration **0801** (on 0800) widens `tenant_entitlements_module_check`, no backfill (dark).
- **Protected paths** (`docs/architecture/protected-paths.md`): `tax/compute/entity/` and `workpapers/compute/` named as red files.
- **Import-linter:** `pyproject.toml` gains an independence contract between `tax.compute.entity` and `tax.compute.individual`. The package `tax/compute/entity/` is reserved; the compute contract already covers it through `tax.compute`.
- **Test:** `backend/tests/unit/tax/test_t05t04_protected_bundle.py`.
- **Rollback:** revert. 0801 is expand-only and its downgrade restores the old CHECK.

## Partials (flagged)
- **Ledger and adjustments condition rows for tax work items:** the matrix has no per-work-item-kind condition. The rule ("independence is not required for tax") needs a compiler feature, or a `tax_` sibling of `adjusted_tb.read` and `account_mapping.propose`. Proposed for N's review (A-06/A-03 own those files); not added, so no row compiles with the wrong meaning.
- **`make check-fast`:** runs at the S35 end pass.

## Progress log
- 2026-11-10: built; generated files regenerated with the codegens.
