---
id: TASK-7948
title: "W-02-T21: WB-03 run arc (PlanCard, gathering and results on the thread, Save to Files with Undo, O4 preview, Retry those 3, cancelled line)"
plan_key: W-02-T21
spec: SPEC-653  # W-02 §3.6–§3.8; WB-03 a, a2, b–g, d2
acceptance_criteria: [AC-P1, AC-P2, AC-G1, AC-W1]  # WB-03 states pass with axe; no Approve control for a non-owner
risk_zone: green
status: in-review
branch: w02-t21-wb03-run-arc
worktree: /Users/ayushkbhatia/Accrued/abacus-s43
created: 2026-11-14
updated: 2026-11-14
---

## Plan
- BE (red seam, DEC-4943): `agents/commands.py` `_head` accepts a firm-level run for its
  initiator (firm-level authorise), `read_plan`; `runs_v2_contract.py` `GET /{run_id}/plan`;
  route introspection list. Client regenerated.
- FE: `screens/WB-03/{PlanCard,copy}.tsx`, `index.tsx` (thread with the plan slot and the
  preview); `screens/WB-01/Thread.tsx` (plan slot, ledger retry scope, Save to Files approval
  with Undo, artifact intents).
- Tests: `apps/web/src/screens/WB-03/WB03.test.tsx`.

## Partial
- The gathering card ("120 of 241 · 50 %"), metric cards, result cards and FileArtifactRow are
  the kit's rows on the session's items; a firm-level run's step progress does not reach the
  session as items until the run streams to its session (P-10's child-run items), so on staging
  they appear only as the run records them.
- "Retry those 3" uses the kit's Retry label on the failed step row.
- A firm-level run's trace (WB-09) still reads 404 (traces stay engagement-only).

## Progress log
- 2026-11-14: built; tsc clean; tests written, not run (S43 end pass).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-4943 | firm-level run commands for the initiator; plan read; the arc on the thread | no |
