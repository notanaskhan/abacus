---
id: TASK-7522
title: Q-03-T258 CL-1 consolidation of the SPEC-032 comments into P-05 threads
plan_key: Q-03-T258
spec: SPEC-650  # P-05 §2.3 CL-1; ADR-236 decision 1
acceptance_criteria: [AC-1]  # existing threads read identically before and after; no comment row updated in place
risk_zone: red
status: blocked
branch: q03-t258-cl1
worktree: /Users/ayushkbhatia/Accrued/abacus-s39
created: 2026-11-12
updated: 2026-11-12
---

## Objective
Re-own `comments`, `comment_mentions`, `comment_redactions` and `comment_reads` in `collaboration`
as `request_item` and `evidence_version` threads (ids and sealed bytes preserved), make the legacy
routes thin wrappers, move SHL-14 and POR-04 onto C-29, retire `comment.mentioned` for
`mention.created`, and drop the `thread_*` tables one train later.

## Why blocked (DEC-4522)
P-05 §2.3 runs CL-1 "after every firm has `collaboration.v2` on". P-05-T16 (TASK-7316) left the
canary flip (both founders, Tuesday slot) and the staging rollback rehearsal open: no firm has the
flag on yet, and there is no staging. CL-1 rewrites the live request and evidence comment paths
(SHL-14, POR-04, the client thread), so it is not built ahead of the flip: a consolidation with no
copy of the canary's threads to prove equivalence on would change live comments unverified.

## Plan (for the row when it unblocks)
1. Expand: `collaboration` gains read paths over the four tables (registry ownership moves from
   `requests`; `banned_patterns._check_table_ownership` follows); `request_item` and
   `evidence_version` register as anchor kinds (`anchors.LIVE_SPEC032_KINDS` empties).
2. Fold: one migration copies each v2 `thread_*` row onto the legacy tables with ids and sealed
   bytes preserved (insert-only; nothing updated in place); `mention.created` replaces
   `comment.mentioned` (both already feed the kind `mention`).
3. Wrap: `requests/comments.py` routes call collaboration's services; SHL-14's Comments tab and
   POR-04's client thread mount C-29.
4. Contract (next train): drop `thread_*`.
5. Prove: Q-03-T259's suite on a copy of the canary's threads, then the flip calendar.

## Progress log
- `2026-11-12` — Scoped and blocked on P-05-T16's canary flip (DEC-4522); Q-03-T259's suite
  is written now with strict expected failures naming this row.
