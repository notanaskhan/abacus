---
id: TASK-7809
title: "R-02-T13 rest: the seed's attest entries and the portal fixture read one figures book"
spec: SPEC-000  # row (R-02-T13; DEC-3013)
acceptance_criteria: [AC-20]  # the row's acceptance, below
risk_zone: green
status: in-review
branch: lo38-r02-t13-equivalence
worktree: /Users/ayushkbhatia/Accrued/abacus-lo38
created: 2026-11-12
updated: 2026-11-12
plan_key: R-02-T13
---

## Objective
"make seed-demo and fixture mode show identical data, and seed tests foot". Close the equivalence half for the attest entries.

## Delivered
- Book: `aje_1_lines` and `paje_2_title`, from AUD-16's spec.
- Fixture `portal-r02.ts`: AJE-1's lines were wrong (1210/4110, labels swapped) and now follow the book. Test added in `portal-r02.foot.test.ts`.
- Seed `completion_slice.py`: PAJE-2 now carries AUD-16's title and the book's three lines (the totals don't change). Test added: `tests/unit/synthetic/test_r02t13_seed_matches_book.py` (4).
- Ran: synthetic, scenario goldens, c18/c10 and assurance unit suites (1,644); web fixtures and POR-08 (644).

## Open
- Not seeded: Copperleaf's posted entries (fixture only; the portal never posts) and Meera's K-1 (POR-13's data).
- No full `make seed-demo` load was run against a database for this change.

## Progress log
- 2026-11-12: built and tested.
