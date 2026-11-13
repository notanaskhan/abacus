---
id: TASK-7733
title: S41 leftovers inside the rows' own scope (after the S41 merge and its CI fix)
plan_key: S41-leftovers
spec: SPEC-651
acceptance_criteria: [AC-F5]  # each leftover's row keeps its own criteria; listed per item below
risk_zone: amber
status: in-progress
branch: s41lo-txp06-signoff
worktree: /Users/ayushkbhatia/Accrued/abacus-s41
created: 2026-11-13
updated: 2026-11-13
---

## Objective
Build what the S41 task files left partial that needs no later row, one PR per item (`[skip ci]`),
tests and gates at one end pass, one batch merge with CI on the last (owner, 2026-11-13: "Yes,
build them").

## Plan (amber: files, tests, rollback per item)
1. T-05-T44 (TASK-7707): the live TXP-06 host opens SHL-12 at L3 and signs through
   `POST …/allocation-structure/approve`, so the L3 writes the approved version and starts the
   re-run. `SignOffWriter` on SHL-12 (`domain/review/signoffs.ts`, `screens/SHL-12/index.tsx`),
   `screens/TXP-06/Allocation.tsx`; SHL-12 test for the writer path. Rollback: drop the writer
   prop; the button hides again (no `onSignOff`). DEC-4736.
2. T-05-T46 (TASK-7709): of the four routes no later row claims, serve `GET …/general-information`
   and `GET …/partners` (`tax/entity_partners.py`, read-only, through the offshore mask);
   mappings is already served; `PUT …/ownership` stays 501 (DEC-4737). Rollback: restore the
   stubs.
3. W-02-T12 (TASK-7715): dropped: `identity.list_offices` and `files.list_folders` are W-02-T19's.
4. W-02-T10 (TASK-7712): AC-C4's summary lines (`workbench/session_context.py`; exports
   `assurance.api.ebp_plan_facts`, `control_exceptions`, `review.api.sign_off_ladder`; workbench may
   import review). The extra picker kinds are not in the spec (not a gap). DEC-4738. Rollback:
   revert the three summary parts.
5. W-02-T13 (TASK-7714): the J11 thread and WB-02's Northwind context scenario.
6. P-02-T12 (TASK-7722): the palette's context-bound actions (P-02-T10, merged #1858).
7. F-07-T13/T14 (TASK-7725/7726): the `./graph` subpath of `@abacus/ui`.
8. End pass: check-fast, pyright, eslint/tsc, the touched suites, Q-03-T274 `pnpm audit` and the
   T275/T276 consumer suites under the test lock; one security read of the diffs.

## Progress log
- 2026-11-13: item 1 built (#1935, `s41lo-txp06-signoff`).
- 2026-11-13: item 2 built (`s41lo-entity-reads`): `tax/entity_partners.py`, the two routes, stub
  test's BUILT set, client regenerated; `PUT …/ownership` stays 501 (DEC-4737). Found: S42's
  `GET …/issue-assignees` is served but missing from the stub test's BUILT set (main red; S42's).
- 2026-11-13: item 3 dropped (W-02-T19's tools); item 4 built (`s41lo-context-lines`).
