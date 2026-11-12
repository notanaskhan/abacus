---
id: TASK-7324
title: "T-04-T32 rest: J06's review slice on the full stack (j06 8, 8b); the tax_workspace seed loads on a fresh database"
spec: SPEC-649
acceptance_criteria: [AC-13]  # §3.13 the live path (the full-stack walk)
risk_zone: green
status: in-review
branch: s37-t04t32-fullstack
worktree: /Users/ayushkbhatia/Accrued/abacus-s37
created: 2026-11-12
updated: 2026-11-12
plan_key: T-04-T32
---

## Objective
TASK-7320 left the full-stack and staging projects `fixme` "until T-04-T29's live hosts and
staging". The live hosts are on main now (#1720), so walk what the seed supports on the full stack.

## Found
- The `tax_workspace` slice (T-04-T28) did not load on a fresh database. Its events carry their
  business times (Aug 25 to 28). The loader replays by `at`, and the firm, Feld's engagement and
  his return are created at setup (Sep 1, 8:00 AM). So the first workspace event ran before the
  firm existed (`NotFound: tax_return`) and the load stopped. Its unit test checked the figures,
  not a load.
- The slice did not turn on `tax.review_workspace` or `tax.individual_workpapers`, so every
  workspace route answered 404 on a seeded stack.
- The full-stack adapter checked for the chooser or "Work email" the instant `/` began loading,
  before the SPA redirected to the sign-in server, so the persona was never signed in. The
  harness now waits for one of the chooser, the email form or the signed-in shell (the Modules
  navigation).
- TAX-05's live Worksheets drew the API's Decimal string as it came ("307900.00"), where the
  artboards show "307,900". It now goes through the kit's `amount(…, "whole")`. The unit test
  fixture had sent pre-grouped strings ("598,030") that the API never sends; it now sends the
  API's shape, and the test asserts the grouped display.

## Built
- `tax_workspace_slice.py`:
  - The two flags are set on the synthetic firm.
  - An event whose business time is before setup replays one second apart from `REPLAY_FROM`
    (Sep 1, 8:01 AM), in its business order. It carries the business time as `data["at"]`, the
    pattern of the review slice's `saved_at`.
  - The loader's four Feld handlers stand the clock on `data["at"]`, so the issues still read
    "raised Aug 25".
- `tests/unit/tools/test_t04t28_tax_workspace_slice.py`: the event count includes the two flags,
  and a new test checks that no event replays before setup and that each carries its business
  time.
- `apps/web/e2e/journeys/J06-1040-season.spec.ts`, a full-stack describe:
  - j06 8: Samuel opens Feld's issues (TAX-06 live), and the box 18A issue is open.
  - j06 8b: Sch E p2 — Ridgeline, picked on TAX-05's live Worksheets, shows "Net rental real
    estate income" 307,900 and "Sign off…".
  - Both open Feld's 1040 from the returns board ("Open row") and take its id from the URL; the
    SPA keeps its bearer token in memory, so a step cannot call the API itself. Both run axe and
    INV-1 to INV-5.
  - The describe is skipped in the fixture project, where the artboard describe walks it, and is
    `fixme` on staging.
- Verified locally on a worktree stack (`make worktree-env`, `make dev`, `make seed-demo
  SNAPSHOT=E0 HOLDOUT=fairhaven_ebp SLICE=tax_workspace`, 1,237 events replayed): `make
  journeys-full` on this describe gives 2 passed and 2 fixme.

## Partial
- j06 6, 7 and 10 on the full stack stay `fixme`. The seed has no drafter run, no approval
  timeline for the 41 documents and no Ridgeline draft K-1 activity (T-04-T28's partial).
- Nightly CI seeds `SNAPSHOT=E0` without `tax_workspace`. There the two steps find no Feld 1040
  and read `fixme` (not failed). Adding the slice to the nightly seed changes data for every
  full-stack journey, so it is left for the next end pass to decide.
- Staging: the three nights with the fake CCH and fake Textract.

## Progress log
- `2026-11-12` — Built (S37 follow-ups).
