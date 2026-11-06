---
id: TASK-3393
title: N-04-T16 the response chain, run whole: decision, draft, letter, envelope
spec: SPEC-000  # row (N-04-T16)
acceptance_criteria: [AC-1]
risk_zone: red
status: in-review
epic: N-04
plan_key: N-04-T16
branch: s28q-n04-chain
worktree: /Users/ayushkbhatia/Accrued/abacus-s28
created: 2026-11-07
updated: 2026-11-07
---

## Objective
DEC-2382 left the sign-off and signature chain unrun against a loaded firm. Run it from analysis through the sealed letter and the envelope draft.

## Plan
One Postgres test through the services: analysis, Request decision, the signer's decision, draft, regenerate, edit, send for signature, then read the sealed snapshot and compose the letter from it. Fix what stops it.

## Progress log
- 2026-11-07: built. 188 passed across the N-04-T21 load file, notice and reporting unit tests; new override and position units pass. Signing itself isn't run here: the envelope is a draft with no signers, and mark sent still patches readiness.

## Decisions made during this task
DEC-2392
