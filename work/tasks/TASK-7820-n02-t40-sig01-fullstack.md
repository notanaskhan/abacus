---
id: TASK-7820
title: "N-02-T40 rest: SIG-01's walks on the full stack; the other signature steps name what they wait on"
spec: SPEC-000  # row N-02-T40
acceptance_criteria: [AC-1]  # the specs pass on the harness with INV-1..5 and axe
risk_zone: green  # e2e specs only
status: in-review
branch: lo39-n02-t40
worktree: /Users/ayushkbhatia/Accrued/abacus-lo39
created: 2026-11-13
updated: 2026-11-13
plan_key: N-02-T40
---

## Objective
N-02-T40's specs exist (TASK-2535) but every full-stack step was `fixme` on "M13". SIG-01 is
routed now (`/signatures`, N-02-T42) and the nightly's `signatures` seed slice holds the hub's
envelopes, so SIG-01 walks live; the rest name their real blocker.

## Plan
- `sig-01-hub.fullstack.spec.ts`: on the full stack, Grace opens `/signatures`; E2's row opens the
  drawer (a), the To send tab lists Harborview (b), Completed lists Summit Line (c); f picks three
  out-for-signature rows and reads "3 selected" / "Remind 3…" (nothing is sent). SIG-01 e stays a
  fixture artboard: no envelope is declined on Sep 14.
- `support.ts`: `hubTab`, and the reasons `BUILDER_ENTRY`, `LETTER_ENTRY`, `NO_DECLINED`.
- SIG-02, ENG-04 and POR-06 g: `fixme` on the full stack with those reasons (no in-app path opens
  the builder on a seeded draft; ENG-04 needs the engagement id the SPA holds in memory; no
  declined envelope is seeded). Staging and the canary stay on M13 (hosted sign-in).

## Progress log
- 2026-11-13: built; to run in the lo39 end pass (local full stack, Sep 14 seed with `signatures`).

## Decisions made during this task
None.
