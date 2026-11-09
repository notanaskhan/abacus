---
id: TASK-6314
title: A-07-T28 AUD-21 representation letter in fixture mode on T10
spec: SPEC-644  # handoff AUD-21
acceptance_criteria: [AC-1]
risk_zone: green
status: in-progress
epic: A-07
plan_key: A-07-T28
branch: s32-a07-t28
worktree: /Users/ayushkbhatia/Accrued/abacus-s32
created: 2026-11-09
updated: 2026-11-09
---

## Objective
AUD-21 on A-07-T11's fixture states: structure pane, paper with DRAFT watermark, tabs, the
primary action per status.

## Plan
- `screens/AUD-21/{copy.ts,RepLetter.tsx,index.tsx}`; tests `AUD-21.test.tsx`.

## Progress log
- `2026-11-09` — Built; not type-checked or run (end pass). Partial: the canvas is not yet
  mounted in the AUD-02 cockpit's Completion › Representation letter row; citation markers [1]–[4]
  and their lighting of toggle rows, Preview as client and the SIG-02 overlay prefill (callbacks
  only) wait for A-07-T33's live wiring; the paper is the E0 artboard's words, not C11's render.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-3014 | Primary action by status; toggles local in fixture mode; A-07-T11's state keys win over the handoff's letters | no |
- `2026-11-09` — S32 end pass: gates, unit, contract, S32 integration and web suites run; fixes folded into the end-pass PR. Status partial.
- `2026-11-09` — Partials round (branch s32p-a07-t28-mount, DEC-3030): opened inside the AUD-02
  cockpit from AUD-19's checklist chip, Back returns; test `screens/AUD-02/completionLetters.test.tsx`.
