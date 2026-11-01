---
id: TASK-2803
title: I-01-T20 ADR-078 AC tests for HOME-02's UI and the activity sources
spec: SPEC-000  # I-01-T20 row and docs/screens/HOME-02.md
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
epic: I-01
plan_key: I-01-T20
branch: s23-i01-t20
worktree: /Users/ayushkbhatia/Accrued/abacus-s23
created: 2026-11-01
updated: 2026-11-01
---

## Objective
- **[AC-1]** "The suite is committed before I-01-T19 opens for review and passes on main without
  edits by AY's session."

## Plan
`apps/web/src/screens/HOME-02/__ac__/home02.ac.test.tsx`, from I-01 §3 F7–F9: INV-1 (no gate verb
on agent-owned elements; gate verbs are HumanActions), rationale before Decide, bulk refuses
blocked and open-note items (AC8.1), reassign lists only server candidates and reassign/snooze wait
for the server (AC8.2–AC8.4, DEC-24), attribution through formatActor (INV-5), allowlisted activity
events only (HOME-01 `activityLines`). Sections 3 and 4 describe I-01-T19, which is stacked on this
branch and must pass them unedited. No production code. Rollback: revert.

## Progress log
- `2026-11-01` — written before I-01-T19; prettier and eslint clean. Run at the S23 end review,
  with T19 merged (sections 3–4 fail on main until T19 lands; the two merge in one batch).

## Decisions made during this task
None.
