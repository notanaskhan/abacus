---
id: TASK-8025
title: "W-02-T24 part 2: independent tests for W-02-T19, T20 and T23 part 1"
spec: SPEC-653
acceptance_criteria: [AC-W1, AC-W5, AC-Q2]
risk_zone: red
status: in-review
branch: w02-t24-independent-part2
worktree: /Users/ayushkbhatia/Accrued/abacus-s44
created: 2026-11-14
updated: 2026-11-14
plan_key: W-02-T24
---

## Objective
ADR-078 independent tests for N's red work that landed after part 1 (TASK-8013): W-02-T19 session plans, W-02-T20 run artifacts, W-02-T23 Save to Files part 1.

## Plan
1. [x] `tests/unit/workbench/test_w02t24_independent_part2.py`, from SPEC-653:
   - plan validation: a declared save with a holding approver passes; an approver who lacks the action, a write with no approver, an undeclared write and a dependency out of level order fail;
   - reads declared once at their largest count;
   - the write line and the access sentence are code's;
   - the agent never holds `file.save`;
   - the attach-only key.
2. [x] Lint debts from S44 round 1, found by `banned_patterns`:
   - two `Any` casts in part 1 now carry reasons;
   - bare type ignores in the closes, C9 v2.1 and W-02-T25 tests now carry reasons;
   - the glossary's "Don't use" cells for C-01 (`posted`, `query`) and T-07 (`finding`, `paragraph`, …) were over-broad. L12 flagged audit and workbench code ("finding_communications", "Posted", "Paragraph", "query"), so those cells now read "—". The "Ties" ban stays in `copy-bans.test.ts`, scoped to TXT-02 and TXT-04.
3. [ ] The J11 API-level journey (b1 to b3) and the database halves: grant `not_before`, Undo, consumption after the approver loses `file.save`, the walled drill. These run with the end pass.

## Progress log
- `2026-11-14` — Steps 1–2 built. ruff, pyright and banned_patterns clean on the touched files.
