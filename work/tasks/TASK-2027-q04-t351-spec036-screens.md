---
id: TASK-2027
title: Q-04-T351 SPEC-036 screen acceptance
spec: SPEC-036
acceptance_criteria: [AC-6, AC-9]
risk_zone: red
status: in-review
epic: Q-04
plan_key: Q-04-T351
branch: s15n-q04-t351
created: 2026-10-29
updated: 2026-10-29
---

## Objective
SPEC-036 AC-6 (the screens say AI is off) and AC-9 (loading, empty, error, not-allowed) on
ADM-04's opt-in and agent-stage band and the engagement-exclusion control (DEC-1063).

Acceptance (backlog row): "SPEC-036 is marked done before Tue Jun 1 with AC-6 and AC-9 passing,
or M9 dossiers record it open with the owning task and no real firm sees an AI-excluded
engagement without the AI-off state."

## Built
- ADM-04: the restricted "role" state on a 403. The exclusion control: loading, error and
  restricted states.
- Tests: `screens/ADM-04/spec036.test.tsx`, `legacy/spec036exclusion.test.tsx`.
- SPEC-036 §10: open on AC-6 (no ENG-02 mount; proposed to P-07).

## Progress log
- 2026-10-29: written (S15 group B); run at the end review.
