---
id: TASK-7409
title: "T-05-T21: Form 1065 form-line reference sets (C21 kind tax_form_lines) for TY2025 (seed) and TY2027 (pilot returns): Schedule L, Form 8825, Schedule K and M-2, plus the M-1 and M-3 keys, loaded through K-02's admin import with two-person publish; golden fixtures pin the published hash"
spec: SPEC-500
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
branch: s38-t05-t21
worktree: /Users/ayushkbhatia/Accrued/abacus-s38
created: 2026-11-12
updated: 2026-11-12
plan_key: T-05-T21
---

## Objective
The entity workbook's line keys are a published C21 reference set per tax year, never constants.

## Plan (amber)
- C21 additive: kind `tax_form_lines` (`reference_sets_contract.TaxFormLine`,
  `TaxFormLinesPayload`), registered in `KINDS`, the CLI's diff identity (`key`), migration 0832
  widening `reference_sets_kind_check`, reader `tax_form_lines_for` exported from `platform.api`.
- Data (public law, outside git, DEC-76): `refdata-drafts/ty2025/` and `ty2027/`
  `tax_form_lines-1065-ty*.draft.json`, 112 rows each (generator kept in the session scratchpad);
  their hashes pinned in `backend/tests/golden/reference_sets/tax_form_lines.json` with the
  mappable keys and the totals; CPA memo `docs/quality/golden-reviews/tax-form-lines-1065@1.md`.
- Tests `tests/unit/tax/test_t05t21_tax_form_lines.py` (9 pass): kind and identity, row
  refusals, form 1065 only, both hashes pinned, the mapper suite's keys ⊂ the mappable keys.
- Rollback: downgrade 0832; nothing reads the kind until T-05-T26.

## Partial
- Publishing is a human step: the tax CPA signs the memo, then `abacus_tools.refdata draft` and a
  second person's `publish` on staging (two people). TY2027's Form 1065 is not released, so its
  draft carries TY2025's lines and waits for the forms.
- "Golden fixtures pin the published hash": the fixture pins the reviewed draft's hash; a
  published version's `payload_hash` must equal it (checked when the set is published).
- `make generate` for the new `ReferenceSetKind` member at the end pass.

## Progress log
- `2026-11-12` — Built (S38). 9 unit tests pass; lint and types clean.
