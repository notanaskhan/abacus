---
id: TASK-8509
title: "C-02-T10: Design follow-ups and copy deltas (docs part)"
spec: SPEC-700
acceptance_criteria: [AC-11, AC-20, AC-21]
risk_zone: green
status: in-review
branch: c02-t10-design-deltas
worktree: /Users/ayushkbhatia/Accrued/abacus-s49
created: 2026-11-17
updated: 2026-11-17
plan_key: C-02-T10
---

## Objective
Spec section: docs/plan/epics/C-02.md §0.1 (DF-19, DF-23), §5. DF-23 Rejected row and Approved before Delivered; DF-19 Recorded-externally variants and Export instead; POR-16 W1 consent copy v2 will/won't list; CLS-07g revised to DEC-69; CLS-13d revised to Export IRIS file, Mark filed, Record acceptance; vendor-link channel unavailable; Elena Ruiz Design decision.

## Plan (green)
1. Screen contracts `docs/screens/CLS-07.md`, `CLS-08.md`, `CLS-11.md`, `CLS-13.md` (new, header plus a 'Design deltas' table each; the screen tasks write the rest) and a deltas section in `POR-16.md`.
2. Each row names the handoff screenshot it amends and the build answer.

## Progress log
- `2026-11-17` — Built in the S49 sequential stack (DEC-5509). Partial by design: the deltas are recorded against the handoff's screenshots; new design frames (a designer's annotated artboards) are not made in a solo session. None needs a backend change outside the C-02 backlog. Gates and tests run once at the S49 end pass (build first, test last).
