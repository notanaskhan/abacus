---
id: TASK-6315
title: A-07-T29 AUD-22 governance communications in fixture mode on T10
spec: SPEC-644  # handoff AUD-22
acceptance_criteria: [AC-1]
risk_zone: green
status: partial
epic: A-07
plan_key: A-07-T29
branch: s32-a07-t29
worktree: /Users/ayushkbhatia/Accrued/abacus-s32
created: 2026-11-09
updated: 2026-11-09
---

## Objective
AUD-22: the required communications with clocks, recipients, Built-from links, and the selected
letter's paper, frames a (planning awaiting approval), b (sent, acknowledged), c (completion).

## Plan
- `screens/AUD-22/{copy.ts,Governance.tsx,index.tsx}`; tests `AUD-22.test.tsx`.

## Progress log
- `2026-11-09` — Built; not type-checked or run (end pass). Partial: frames read the handoff's E0
  rows, not A-07-T11's `aud22` fixture (which has no rows) nor A-07-T26's live read; not mounted in
  the cockpit; citation markers and source-row lighting, Recipients and History tabs' bodies and
  the approve-and-send dialog (fresh MFA) wait for A-07-T33's wiring.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-3015 | Frames from the handoff's E0 rows; Approve & send only with the server's action | no |
- `2026-11-09` — S32 end pass: gates, unit, contract, S32 integration and web suites run; fixes folded into the end-pass PR. Status partial.
