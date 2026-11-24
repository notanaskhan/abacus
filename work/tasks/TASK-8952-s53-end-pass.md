---
id: TASK-8952
title: "S53-END: S53 end pass: gates, tests, security review"
spec: SPEC-000
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: amber
status: in-review
branch: s53-end-pass
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-23
updated: 2026-11-24
plan_key: S53-END
---

## Objective
Bring the S53 stack tip through stage-1 gates (ruff, pyright, banned patterns, import contracts, web lint and types) before the targeted and integration tests and the batch merge.

## Done
- pyright: 9 errors fixed
- banned patterns: 24 violations and 95 unexplained ignores fixed or decided (DEC-5940)
- unit, web and kit suites green (weasyprint's libgobject is missing on this machine: the
  reporting PDF tests error locally, environment only)
- migrations 1010 and 1012: two foreign keys that broke every DB test fixed (1010 drops the FK to
  `methodology_request_items`; 1012's sample-set FK is tenant-composite)
- integration: 23 failing files fixed:
  - real defects: presence routes recorded no check, so the route guard answered 500 (now
    `authorise_own` plus the owner's object read); `_LOCKED` dropped v1 archives (now v1
    `created_at` or a locked v2 `locked_at`); the TB hand-off locked rows with `FOR UPDATE` on
    an insert-only table (now a transaction advisory lock on the target); the two-year accept
    computed the comparison before the check (now checks first); planning and postponement
    no-op inserts left a unit of work with no audit event (now `_Nothing`); `planning.read`'s
    consent condition failed closed for every person (DEC-5941)
  - test fixes: AC tests sent malformed requests (bodies, the `Idempotency-Key`, query windows);
    seeds (one transaction for a snapshot and its lines, the site's own assurance item, a
    `tax_returns` row, a published floor); the K-03 insert column joins the schema contract
- bundle budget: the firm initial load read 315.3 KB of 300 (main 293.3). SHT-01's sheet grid made
  the States kit's `ErrorRow` live, and its `StatusDisc` pulled the whole status registry (~18 KB
  gzip) into the shared eager chunk: the disc and its labels moved to registry-free modules
  (`packages/ui/src/disc.ts`, `components/status-disc.tsx`, both re-exported from their old homes),
  297.0 KB now. AUD-06 imported the hand-off gate through the tax barrel (+2.4 KB on the AUD-02
  cockpit, 140.9 of 140): the gate is now its own entry `domain/tax-handoff` (139.0)
- security review of the red and amber diffs: no findings beyond the defects above

## Progress log
- `2026-11-23` — 2026-11-24: gates fixed; full check-fast re-run next.
- `2026-11-24` — integration failures fixed (above); re-run of the 23 files and check-fast before the batch merge.
