---
id: TASK-7636
title: P-02-T10 rest — the palette's context-bound actions
plan_key: P-02-T10
spec: SPEC-000  # docs/screens/SHL-02.md; P-02 epic acceptance
acceptance_criteria: [AC-1]  # SHL-02a Actions bound to the top Clients result
risk_zone: green
status: in-review
branch: p02-t10-context-actions
worktree: /Users/ayushkbhatia/Accrued/abacus-s40
created: 2026-11-13
updated: 2026-11-13
---

## Objective
Finish the Actions of SHL-02a and f, left out in TASK-7620: the actions bound to the top
Clients result (P-02 AC: "New engagement for ‹client›…" and "New to-do on ‹client›…").

## Plan
- `screens/SHL-02/{copy,index,SHL-02.test}`: `contextActions` from the top client row, hidden
  while a target is planned in production (`hrefOf`), omitted with no client; tests a, e, f.
- Rollback: revert.

## Partial
- "Run an agent on ‹client›…" waits for W-02's WB-01 target, "Message ‹contact›…" for N-03, and
  "Open board · ‹audit›" for K-04 (P-02 epic, downstream registrants).
- SHL-17's `?ov=todos:new:client:<id>` overlay is P-05's to register; the row stays hidden in
  production until then.

## Progress log
- `2026-11-13` — Built (DEC-4631).
