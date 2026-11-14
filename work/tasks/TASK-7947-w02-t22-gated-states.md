---
id: TASK-7947
title: "W-02-T22: unavailable and gated states (DF-04, Request consent, flag-off, Agents and Connect)"
plan_key: W-02-T22
spec: SPEC-653 (W-02 §3.9)
acceptance_criteria: [AC]  # words and a disabled composer with its reason; no control the server would refuse
risk_zone: green
status: in-review
branch: w02-t22-gated-states
worktree: /Users/ayushkbhatia/Accrued/abacus-s43
created: 2026-11-14
updated: 2026-11-14
---

## Plan
- Kit `ChatThread`: `composerDisabledReason`, `composerAction` (additive).
- WB-01 `Thread.tsx`: `availabilityOf` over `GET /v1/agents/capabilities`; `index.tsx`: Agents
  and Connect tabs' planned words; `copy.ts`.
- Tests: `apps/web/src/screens/WB-01/WB01.gated.test.tsx`.

## Partial
- "Request consent" needs a host action (C19's consent request route sits with T-01's consent
  screens); WB-01 passes none yet, so the button does not render.

## Progress log
- 2026-11-14: built; tsc clean; tests written, not run (S43 end pass).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-4942 | DF-04 words, fail closed, planned tabs | no |
