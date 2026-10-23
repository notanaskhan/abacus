---
id: TASK-921
title: Brightwater Hale binder slice - 241 TY2025 binders, Feld, Copperleaf close intake, golden footing tests (P-06-T08)
spec: SPEC-319
acceptance_criteria: [AC-10]
risk_zone: amber
status: done
epic: P-06
plan_key: P-06-T08
branch: p06-t08-binder-slice
created: 2026-10-23
updated: 2026-10-23
---

## Objective
"The loaded tenant shows 1+48+0+40+152 = 241 and every section 5.4 figure foots in tests." (SPEC-319 AC-10: "the Brightwater Hale tiles foot to 241".)

## Plan (amber: written before building)
- **New file:** `backend/src/abacus_tools/synthetic/scenarios/brightwater_hale/binders.py`. It
  registers the opt-in `binders` slice, like `shell`. `build()` keeps its default, so
  `SCENARIO_HASH` and `SCENARIO_VERSION` don't change.
- **Loader:** four bootstrap handlers in `loader.py`, writing as the owner with audit rows. This
  is the pattern the scenario already uses for the firm, its people and F-04-T20's audits.
- **No edits to:** product code, routes, migrations, flags, the matrix or any registry. Binder
  tables are migration 0100.
- **Tests:**
  - `tests/unit/scenarios/test_binders_slice.py` (16): every §5.4 figure the slice carries,
    before load.
  - `tests/integration/test_scenario_binders.py`: E0 plus `--slice binders` in its own Postgres;
    the figures as rows; a re-run writes nothing.
- **Rollback:** revert the commit. The slice is opt-in.

## What changed
- **Return roster (DEC-146).** 224 TY2025 `tax_return` work items (with `tax_returns` rows) on
  214 `tax_compliance` engagements, 10 of which hold two returns. Offices read 98 / 64 / 62.
  79 returns are open and 145 done. Forms come from §9.3, §9.7 and E5–E10, otherwise from the
  client's kind. The Feld engagement and work item keep the TS seed's ids and team (DR, SI, OB,
  KO), opened Feb 2 and due Oct 15.
- **241 TY2025 binders.**
  - Tiles: 1 Draft, 48 Published, 0 Unpublished, 40 Complete, 152 Closed.
  - Parts: 224 "2025 Binder" + 17 "2025 Binder pt 2".
  - The BND-01 rows and Osterberg's are verbatim: status, Feld published Feb 3 by Kevin Osei,
    marked done by Owen Calder (Jun 1), Eleanor Calloway (Sep 9), Dr. Sofia Lindqvist (Aug 28)
    and Elena Varga (Aug 30), Whitley closed Apr 10, and last client activity into
    `binder_activity`.
  - Those four people are client users on the sink domain.
- **Feld (BND-02a).** Nine `tax_portal` categories with their glyphs. Seven requests (5 received,
  the K-1 firm-provided) give 5 of 7, 71%, 2 open.
- **Copperleaf close intake (CLS-03, SHL-14d).**
  - The "2026 Close" engagement (PR, RM) and its "August 2026 Close" (`close` work item, period
    2026-08, due Sep 10).
  - A published `close_intake` binder with five `close` categories and 9 requests (8 recurring
    Sep 1 + 1 ad hoc Sep 11, 7 received).
  - Square payouts is Pending incorporation; the six others received are Incorporated by RM.
- **Northwind PBC and the Keystone bridge letter** ("Requested Sep 1 · due Sep 25") are
  F-04-T20's. A test foots them here.
- **TY2026.** No binders (BND-01d).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-146: how the 224 returns, 214 engagements and generic binder states are allocated | No source lists them; DEC-47 says 184 clients back them; T-02-T11 owns the final shape | no |
| DEC-146: Osterberg is Published in the database; BND-01c's unpublish is a fixture override | BND-01a and the acceptance read 0 Unpublished at the same instant | no |
| DEC-146: only Feld and the close intake carry requests | No source lists the other binders' requests; their "n of m" stays declared data | no |
| DEC-146: the SURL Draft and its 31 files wait for F-04-T25 | P-06 §5.4 says they use F-04-T25's documents and citation regions | no |

## Gotchas and discoveries
- **BND-01b live.** Generic Published binders carry no activity date, so "None in 30 days"
  would match more than Fenwick until T-02-T11 or P-06-T11 seeds activity. The unit test foots
  b over the named rows.
- **Prep column.** No binder column holds the preparer. The BND-01 initials are declared data
  (`NamedBinder.prep`) until T-02-T11's assignments.
- **secrets_scan.** It reports `tests/integration/test_binder_lifecycle.py:49` (SECRET-003, an
  `Idempotency-Key` value assigned to `KEY`). That file came from TASK-914 on main; this task
  didn't touch it.

## Progress log
- 2026-10-23: unit 16 passed; integration 3 passed (binders, audit core, the existing loader
  test); scenario and golden suites pass. ruff, pyright, banned_patterns, validate_docs,
  scope_guards and check-generated are clean. secrets_scan reports only the pre-existing
  finding above.
- `2026-10-23` — P-06-T29 golden-figure suite `backend/tests/integration/test_p06t29_binder_goldens.py` (TASK-993): the §5.4 figures the slice carries pass and a seeded change to each fails its golden; the figures it does not carry yet are strict xfails.
