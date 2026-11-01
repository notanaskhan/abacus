---
id: TASK-2719
title: A-03-T16 part four — AUD-11 and AUD-31 fixtures exported from the seed
spec: SPEC-580  # A-03 §5.4
acceptance_criteria: [AC-1]
risk_zone: green
status: in-review
epic: A-03
plan_key: A-03-T16
branch: s22-a03-fixtures
worktree: /Users/ayushkbhatia/Accrued/abacus-s22
created: 2026-11-01
updated: 2026-11-01
---

## Objective
A-03-T16 AC-1's second half: "fixture mode and seed-demo render identical figures for every state
in section 5.4", through `make fixtures` and an equivalence test.

## Done (DEC-1770)
- `fixture_export` profiles; `make fixtures SNAPSHOT=2026-09-24T10:20` writes 10 files (AUD-11 a,
  AUD-11 f, AUD-31 f). Server ids become natural-key stand-ins, so two loads export identical
  bytes (checked by exporting twice).
- `tests/integration/test_a03t16_fixture_equivalence.py` (3 passed; E0's 3 unchanged).
- `apps/web/src/fixtures/seed/sampling.exported.test.ts` (11 passed): the designed figures
  agree; the known gaps are pinned.
- Mapping summary `entity_name` is now the entity's name, not the TB label (found by the export).

## Remaining
1. Northwind Distributions (64, "10 of 64 · Draft", seed 0x7B13C4): the design gives no method.
2. Product call: should approving a later version supersede an earlier *draft* (AUD-11 a shows
   Version 1 struck), or only an earlier approved one (the A-03 §5.4 AC, as built)?
3. The AUD-31 a′–e′ and AUD-11 b–e states are composed in fixture mode; only a, f (AUD-11) and
   f (AUD-31) are exported.

## Progress log
- 2026-11-01: built. The first export diff found one unstable value (a snapshot id inside
  `citation_match_id`); ids inside strings are now swapped too.
