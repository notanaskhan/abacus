# Front-end integration lane, 2027 Q4 (Q-03-T172; part 2 of 2)

The lane takes what a batch breaks on the front end between task branches: fixture-to-live swaps
that broke, kit and template regressions across screens, and merge conflicts in routes and copy
registries. Acceptance: every front-end batch failure of the period is resolved within one working
day. The rules are the Q2 and Q3 records'; this record covers the S26 batches (2026-11-03).

## Measurement
No `ci` run exists for the period: GitHub Actions created no runs on 2026-11-03 after 17:29 UTC,
and the owner merged #1126–#1158 on the local gates (`make check-fast` and the touched suites,
green). The failures below are the S26 end review's and the batch-2 build's own runs, each fixed
the same working day. **The `main` streak from the Q3 record still stands** until one `ci` run on
`main` completes green.

## Failures handled in this lane

| Date | Batch | What broke | Layer that should have caught it | Fix |
|---|---|---|---|---|
| 2026-11-03 | S26 | `link-contract.test.ts` rule 5: BND-03 and TAX-13's contracts listed links in prose | the row (T-03-T02) | Links tables (ED-322) |
| 2026-11-03 | S26 | ESLint over `apps/web`: AUD-08's Edit passed model text as an edit (ADR-065 rule) and a redundant check | the row (A-04-T26) | Edit hands off to the host (ED-323, with a test) |
| 2026-11-03 | S26 | `packages/ui` tests fail with `document is not defined` when vitest runs without the package script | none: tooling | run `pnpm -C packages/ui test` (its script sets `--environment jsdom`), never bare `vitest run` there |
| 2026-11-03 | S26 batch 2 | AUD-04's first use of the C-02 `WorkpaperPane`: text columns without a `type` render through the money cell and crash | the kit's types (an untyped column defaults to numbers) | AUD-04 types its columns (`label`, `text`) |
| 2026-11-03 | S26 batch 2 | AUD-02's cockpit gained EBP-03's canvas beside EBP-02's | integration | AUD-02, EBP-02 and route suites re-run green (71) |

No route or copy-registry merge conflict this period: the stack was rebased once onto `main` with
`decision-log.md` and `capacity-ledger.md` merged as union, and every generated file (the API
client, the provider-terms hash, the route table) was regenerated, never hand-merged.
