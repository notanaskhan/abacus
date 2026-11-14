---
name: tax-engine
description: How to change a tax compute engine (E1–E13) or the entity-return workbook safely — pure compute packages, Decimal and rounding, engine stamps and out-of-date marking, golden cases and the CPA memo per engine version, the closed formula grammar, keep-human writes and §7216 subjects. Use for any change under tax/compute/, workpapers/compute/, or the entity workbook's run steps.
---

# Tax engine pattern

Binding: ADR-050 (code computes, models judge), ADR-237 (the workbook formula grammar), ADR-167
(TRI), ADR-005 (agents propose), chapter 03 §10.1 and chapter 10 §10.9 (engines). Protected: a
change to this file is approved by notanaskhan.

## 1. Where engines live
- Pure packages only: `backend/src/abacus/modules/tax/compute/` (entity engines under
  `compute/entity/`) and `workpapers/compute/` (E13: `formula.py`, `dag.py`). They import only
  `abacus.kernel.numeric` and `abacus.kernel.calendar` (import-linter contract); no clock, no
  database, no I/O, no `eval`, `exec` or dynamic import (banned-pattern tests read them).
- Typed, frozen inputs; `Decimal` at precision 28 with an explicit rounding rule per output;
  splits through `kernel.numeric.allocate()` (largest remainder). Never a float.

## 2. Stamps and versions
- Every persisted output carries `engine_name`, `engine_version`, `inputs_hash`, `computed_at`.
- Bump `engine_version` on any change to an output. A new version marks dependents out of date
  and proposes a recompute checkpoint for a person; nothing recomputes by itself.
- One CPA memo per engine version (`docs/quality/golden-reviews/`, T-05-T39, T-05-T70) before the
  module holds for a real firm (`platform.entitlements.REVIEWED_MODULES`).

## 3. Tests first
- Golden cases with exact `Decimal` equality (`backend/tests/golden/tax/…`), plus Hypothesis
  properties (footing, sign, allocation sums). Write the case before the change.
- The fake engine and the conformance tests run per PR; a real-engine comparison (CCH) is a
  reconciliation (T-05-T61), never an input to a golden.

## 4. The workbook
- Cells are review fields (`workbook_service.write_cells`, insert-only versions). Engines write
  `formula`, `engine_import` or `tb_linked`; a person writes `human` with a citation note; an agent
  never writes a cell. Every run step keeps a person's cells (`engine_may_write`, `keep_human`).
- Formulas: the closed grammar only (SUM, ROUND, IF, MIN, MAX; references; `+ - * / %`). A new
  function is an ADR-237 amendment, a grammar test and a golden first.
- Imports are hostile (ADR-052): cached values only, text or exact decimals, nothing evaluated.

## 5. TRI and models
- Workbook values, memo sections and K-1 boxes are Restricted `tri`. A model never computes a
  figure; it may cite facts code registered.
- Every model call on an entity return names `entity_return_subjects` so the gateway checks the
  §7216 consents (DEC-4928); a step without consent becomes the `consent_7216` question.

## 6. Operate
`docs/runbooks/entity-return-workbook.md` (stuck run, recompute storm, consent revoked mid-run,
engine version out of date, roll back); RB-19 for the CCH bridge.
