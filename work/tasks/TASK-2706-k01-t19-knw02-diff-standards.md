---
id: TASK-2706
title: K-01-T19 KNW-02 c, d and draft-review mode
spec: SPEC-000  # K-01-T19 row and K-01 §3.6
acceptance_criteria: [AC-1]
risk_zone: green
status: in-review
epic: K-01
plan_key: K-01-T19
branch: s22-k01-t19
worktree: /Users/ayushkbhatia/Accrued/abacus-s22
created: 2026-10-31
updated: 2026-10-31
---

## Objective
- **[AC-1]** "KNW-02c and d pass Tier C, and Hannah's v4 draft opens in KNW-02 with the viewer
  empty state and a working diff against v3."

## Scope
**In**: KNW-02 tabs, Diff (tiles, rows, struck-over-green), Standards mapping (rows, default
toggle), Activity, Compare with, draft-review mode; EvidenceTriad `wide`; fixtures (c, d, draft);
gallery; tests.
**Out**: Uploaded files band and a/a2/b (importer, K-01-T21/T23); Change pickers (platform
standards list); Tier C pixel lock (K-01-T25).

## Plan
1. Tests first (`KNW-02.review.test.tsx`). 2. Build on K-01-T18's client. Rollback: revert.

## Progress log
- `2026-10-31` — built; tsc, eslint, prettier clean. Tests run at the S22 end review.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-1756 | layout via a kit option; standards words on the screen | No |
