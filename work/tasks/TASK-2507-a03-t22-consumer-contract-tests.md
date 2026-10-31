---
id: TASK-2507
title: A-03-T22 consumer contract tests for C9 v2 and the sampling API stub
spec: SPEC-580
acceptance_criteria: [AC-18]
risk_zone: amber
status: in-review
epic: A-03
plan_key: A-03-T22
branch: s20-a03-t22
created: 2026-10-30
updated: 2026-10-30
---

## Objective
Chapter 01 §1.3.2 steps 1 and 3 for A-03's two contracts: the consumers (AUD-11, AUD-31) pin the
fields and designed facts they read, in pytest against the stubs and in TypeScript against the
generated client and the OpenAPI document.

## Plan (amber)
- `backend/tests/contracts/sampling/test_sampling_consumers.py`: AUD-11's read fields per schema;
  Northwind v2 (412, 25, 0x5E2A91, 22, the W-3 tie, Version 1 off −182,300.00, first five names);
  Granite Peak's strata 24/1,102/786 → 40 items, 3,698,700.00, 0x7C31B4; human-only actions.
- `backend/tests/contracts/c09_ledger/test_c09_v2_consumers.py`: AUD-31's read fields; Granite
  Peak 128 of 128, 1 of 1, Prepared; BH FS groupings v1's import shape (three sheets, headers) and
  the picker's class order; status words and A-09's reserved states; human-only confirm/edit; no
  adopt route.
- `apps/web/src/fixtures/seed/sampling.ts` (typed fixtures A-03-T11/T12 reuse) and
  `apps/web/src/fixtures/contracts/sampling-mapping.contract.test.ts` (enum coverage of the four
  families, OpenAPI validation, designed facts).
- Rollback: delete the suites; nothing depends on them.

## Acceptance
| Check | Test |
|---|---|
| Fails on a breaking change to the shapes AUD-11/AUD-31 read | the `READS` tables in both pytest suites; `tsc` on the typed fixtures |
| Granite Peak 128 and BH v1 shapes pinned | `test_ac18_granite_peak_128_fits`, `test_ac18_the_bh_groupings_import_shape_is_pinned` |
| Fixtures match OpenAPI | `sampling-mapping.contract.test.ts` |

## Progress log
- 2026-10-30: built (run at the end review). Lane A complete.
