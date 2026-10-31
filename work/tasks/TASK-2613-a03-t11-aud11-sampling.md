---
id: TASK-2613
title: A-03-T11 AUD-11 a, b, d, the sample-set picker and C-20 states
spec: SPEC-580
acceptance_criteria: [AC-1]
risk_zone: green
status: in-review
epic: A-03
plan_key: A-03-T11
branch: s21-a03-t11
worktree: /Users/ayushkbhatia/Accrued/abacus-s21
created: 2026-10-31
updated: 2026-10-31
---

## Objective
- **[AC-1]** "Fixture scenarios a, b and d render with all 25 names and the 13,813,400.00 +
  746,600.00 = 14,560,000.00 tie, and the picker lists Participants and Distributions without
  counts for walled engagements."

## Scope
**In**: `screens/AUD-11/` (the Sample Selection canvas hook `useSampleSelectionCanvas`, copy,
artboard, tests), AUD-02 rendering it for `?section=sample_selection`, fixture handlers and
scenarios (a, b, d, picker, off, not_allowed, loading, error), seed variants (b's draft, the
picker's two sets), gallery board, manifest `fixture`, the screen contract's status line.
**Out**: c, e, f and SHL-14 c (A-03-T15); the live swap of sample sets (the routes answer the
Brightwater fixtures until A-03-T10 builds sample sets, draws and approval; the canvas already
reads through the generated client, so the swap is the data); Save and draw in d calls nothing
yet (T10's `POST …/versions`); the SHL-07 citation popover and SHL-08 source link (planned links).

## Plan
1. [x] Canvas: Population (Source segmented R2 with HR disabled, file, records, hash, both ties
   with tally pills, sampling unit, deviation), Method & parameters (rates as percents from the
   server's ratios, computed size with the cross-check, seed with copy, algorithm), Selected items
   with server search, Versions (Superseded struck; Approved with the person's chip; Prepared ·
   MD), footer Generate (disabled with its tooltip unless approved), the d override banner with a
   required rationale. 2. [x] Picker in the control row (DF-05). 3. [x] C-20: flag-off, loading,
   error, empty; a walled person's 404 shows nothing and no count. Rollback: revert.

## Progress log
- `2026-10-31` — AUD-11 9 passed; AUD-02 and AUD-06 suites 72 passed; eslint and tsc clean.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| — | none (deferrals listed under Out) | No |
