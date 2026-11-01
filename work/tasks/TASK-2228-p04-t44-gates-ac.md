---
id: TASK-2228
title: P-04-T44 independent AC tests for the E7 kit, SHL-10 and SHL-16
spec: SPEC-000  # the backlog row; SPEC-360 and the handoff
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: amber
status: done
epic: P-04
plan_key: P-04-T44
branch: s17-p04-t44
created: 2026-10-30
updated: 2026-11-01
---

## Objective
Independent AC tests (ADR-078) for the E7 kit, SHL-10 and SHL-16 UI: no gate control on
agent-owned elements, uncited disables approval, never optimistic, attribution through
formatActor, Undo calls only the compensating command.

Acceptance (backlog row): "Tests written in notanaskhan's session pass and fail if any approve or
sign-off control appears on an agent-owned element."

## Plan
- `apps/web/src/domain/review/gates.ac.test.tsx`: five groups over HumanAction, ApprovalCard, SHL-10
  (a, c) and SHL-16 (a), with a non-vacuity guard (a person does see Approve) and held server
  answers to prove nothing is optimistic.
- Note: the row asks for notanaskhan's session; built here in the solo Lane 2 (AMENDMENT-solo).

## Progress log
- 2026-10-30: written in S17 Lane 2 on P-04-T43; run in the end review.
- 2026-11-01: merged to main in #800 (201df3e3e).
