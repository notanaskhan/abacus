---
id: TASK-2316
title: T-01-T22 fake CCH Axcess
spec: SPEC-501
acceptance_criteria: []
risk_zone: amber
status: in-review
epic: T-01
plan_key: T-01-T22
branch: s18-t01-t22
worktree: /Users/ayushkbhatia/Accrued/abacus-s18
created: 2026-10-30
updated: 2026-10-30
---

## Objective
A deterministic, synthetic-only fake of CCH Axcess Tax that reads Accrued's export workbook and
emits the engine's files (values V1–V3, diagnostics with both variants, PDFs, e-file status
report), plus the conformance check that the adapter suite and partner files share.

## Plan
- `abacus_tools/fakes/cch_axcess.py` (no product import of it; no module internals: BOUND-001).
- `docs/contracts/tax-engine-bridge.md` §6 file formats; DEC-1362.
- Tests: `tests/unit/fakes/test_t01t22_cch_axcess.py`.
- Rollback: revert.

## Progress log
- `2026-10-30` — built (DEC-1362); unit tests run once (11 pass). Partner sample files do not
  exist yet (F-09-T120): the conformance check runs on the fake now and on them when filed.
  `[skip ci]`.

## Handoff
- **Current state:** built, PR open, held for the S18 batch.
- **Exact next step:** T-01-T19 builds the values adapter against §6 and runs `conformance`.
