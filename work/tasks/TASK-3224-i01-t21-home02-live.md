---
id: TASK-3224
title: I-01-T21 HOME-02 live wire-up
spec: SPEC-000  # I-01-T21 row and docs/screens/HOME-02.md
acceptance_criteria: [AC-1]
risk_zone: green
status: in-review
epic: I-01
plan_key: I-01-T21
branch: s26-i01-t21
worktree: /Users/ayushkbhatia/Accrued/abacus-s26
created: 2026-11-03
updated: 2026-11-03
---

# TASK-3224 · I-01-T21 · HOME-02 live wire-up

**Epic:** I-01 · **Sprint:** S26 · **Type:** FE · **Zone:** green · **Depends on:** I-01-T19, I-01-T20 · **Status:** in-review

## Plan
- `domain/home/queries.ts`: HOME-02's reads move here (`useApprovalsList`, `useDoneGates`, the shared `useGateCounts`), plus `approvalsHref(gateId)`.
- HOME-02 (`index.tsx`, `Detail.tsx`): read through the domain hooks; every gate write (snooze, reassign, decide, bulk sign-off) calls `invalidateGates`, which refreshes counts, lists and the home read together.
- HOME-01: with `home.approvals` on, a Waiting-on-you row links to `/home/approvals?gate=<id>`; off, rows keep opening their host (I-01 AC2.4).
- Seed: `home.approvals` on for the Dev firm and the synthetic firms. Legacy `Review.tsx` untouched until the per-firm flips.
- Test: `HOME-01.test.tsx` "rows with home.approvals" (off: no approvals links; on: each row's href is its gate's).

## Acceptance
- [x] With the flag off nothing on HOME-01 changes (row targets unchanged; test).
- [ ] With it on, Margaret's materiality decision opens selected in HOME-02 on staging: **pending** the batch-close staging deploy.

## Progress log
- 2026-11-03: built; tsc and eslint clean; vitest not run (end pass). The `home.approvals` YAML description still says synthetic-on arrives with I-01-T22; it arrives here.
