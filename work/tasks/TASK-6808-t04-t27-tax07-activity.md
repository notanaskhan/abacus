---
id: TASK-6808
title: "T-04-T27: TAX-07 Activity and Checkpoints states a, b, b2, c, d, e, e2 and f in fixture mode on the T2 single-pane variant"
spec: SPEC-649
acceptance_criteria: [AC-5]
risk_zone: green
status: in-review
branch: s36-t04-t27
worktree: /Users/ayushkbhatia/Accrued/abacus-s36
created: 2026-11-11
updated: 2026-11-11
plan_key: T-04-T27
---

## Objective
All eight TAX-07 artboards render, every approval row names a person and never Accrued Agent,
engine ids run V1 Feb 3, V2 Apr 14, V3 Sep 10, and the empty filter reads 'No events match this
filter.'

## Built
`apps/web/src/screens/TAX-07/`: the 24-event Timeline (76px date column, markers on a hairline,
"{Verb} by {Actor}"), kind filter and live search, checkpoints pane (Current and starred, Approved,
Proposed with Review), the proposed 18A row and SHL-16 steps (b, b2), "No changes needed" with
Issues 3 (c), delivered rows (d), Agent filter and empty filter (e, e2), checkpoint row, star and
Compare… to the host (f), row links to SHL-08, INB-01, TXP-12, TAX-09, SIG-01 and TAX-12.

## Progress log
- `2026-11-11` — Built (S36). Tests written, not run (end pass).

## Partials
- The delivered rows' times other than the two acceptances are not in the handoff; they come
  from the seed's envelope and ack events when the screen goes live (T-04-T29).
- Gallery frame and parity measurement at the end pass.
