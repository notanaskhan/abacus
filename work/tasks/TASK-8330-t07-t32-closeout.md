---
id: TASK-8330
title: "T-07-T32: T-07 close-out: README sections and the fiduciary workpapers runbook"
spec: SPEC-656
acceptance_criteria: [AC-15]
risk_zone: green
status: in-review
branch: t07-t32-closeout
worktree: /Users/ayushkbhatia/Accrued/abacus-s47g04
created: 2026-11-16
updated: 2026-11-16
plan_key: T-07-T32
---

## Objective
Spec section: docs/plan/epics/T-07.md §10.
T-07 close-out: README sections and the fiduciary workpapers runbook.

## Plan (green)
1. `backend/src/abacus/modules/tax/README.md`: the trusts and estates section.
2. `docs/runbooks/RB-90-fiduciary-workpapers.md`: reader refusal, re-segmentation and reopen, K-1 supersede and resend, CCH tie-out differences, the estate shadow label, roll back.

## Progress log
- `2026-11-16` — Built in the S47 sequential stack. Docs written. Partial (human): the `.claude/skills` backend-module and ai-agent notes (protected; N approves), the CPA sign-off of the T-07 goldens for M18, and the TY2027 fiduciary due-date rows through the refdata CLI per environment. Gates and
  tests run once at the S47 end pass (build first, test last).
